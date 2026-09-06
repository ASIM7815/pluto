"""GPT-OSS 120B LLM client (OpenAI-compatible) with a mock planner fallback.

When no API key is configured (mock mode) the client uses a deterministic
scripted planner so the whole agent loop still runs end-to-end for demos.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LLMToolCall:
    """A single tool invocation requested by the model."""
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class LLMResponse:
    """Normalised response from the LLM."""
    content: Optional[str] = None
    tool_calls: List[LLMToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Real API client
# ---------------------------------------------------------------------------
class GPTOSSClient:
    """Client for GPT-OSS 120B via an OpenAI-compatible endpoint (Groq)."""

    def __init__(self) -> None:
        self.api_key = settings.gpt_oss_api_key
        self.base_url = settings.gpt_oss_base_url.rstrip("/")
        self.model = settings.gpt_oss_model
        self.mock_mode = settings.pluto_llm_mock_mode
        self.client: Optional[httpx.AsyncClient] = None
        if not self.mock_mode:
            self.client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=90.0,
            )

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat completion and return a normalised LLMResponse."""
        if self.mock_mode or not self.client:
            return await self._mock_chat(messages, tools)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or settings.pluto_llm_temperature,
            "max_tokens": max_tokens or settings.pluto_llm_max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            logger.info("gpt_oss_request", model=self.model, message_count=len(messages))
            response = await self.client.post(
                f"{self.base_url}/chat/completions", json=payload
            )
            response.raise_for_status()
            data = response.json()
            return self._normalise(data)
        except httpx.HTTPError as e:
            # Some providers use max_completion_tokens for reasoning models.
            if "max_tokens" in str(e) and "unsupported" in str(e).lower():
                payload["max_completion_tokens"] = payload.pop("max_tokens")
                response = await self.client.post(
                    f"{self.base_url}/chat/completions", json=payload
                )
                response.raise_for_status()
                return self._normalise(response.json())
            logger.error("gpt_oss_error", error=str(e))
            # Graceful fallback so the loop still functions on transient errors.
            return LLMResponse(content="Sorry, I hit an error reaching the model.", finish_reason="error")

    @staticmethod
    def _normalise(data: Dict[str, Any]) -> LLMResponse:
        choice = data["choices"][0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason")

        content = message.get("content")
        tool_calls: List[LLMToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                LLMToolCall(name=fn.get("name", ""), arguments=args, id=tc.get("id", ""))
            )

        logger.info("gpt_oss_response", finish_reason=finish_reason, tool_calls=len(tool_calls))
        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=finish_reason)

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    # ------------------------------------------------------------------
    # Mock planner: deterministic multi-step demo agent
    # ------------------------------------------------------------------
    async def _mock_chat(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]
    ) -> LLMResponse:
        """Scripted planner used when no API key is configured."""
        # The latest user message is the actual new instruction.
        user_text = ""
        last_user_idx = -1
        for i, m in enumerate(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                last_user_idx = i

        # Count tools already executed in THIS command (Observe->Reason loop),
        # i.e. tool results appended after the most recent user message.
        executed = sum(
            1 for m in messages[last_user_idx + 1:] if m.get("role") == "tool"
        )

        plan = self._build_plan(user_text)
        plan_seq = list(plan)
        if executed < len(plan_seq):
            step = plan_seq[executed]
            if isinstance(step, LLMToolCall):
                # Ensure a stable, unique id per invocation so the ReAct loop can
                # reference the tool result.
                if not step.id:
                    step.id = f"call_{executed}"
                return LLMResponse(content=None, tool_calls=[step], finish_reason="tool_calls")
            return LLMResponse(content=step, finish_reason="stop")
        return LLMResponse(
            content=plan_seq[-1] if plan_seq else "Done. Anything else?",
            finish_reason="stop",
        )

    @staticmethod
    def _build_plan(user_text: str) -> List[Any]:
        t = user_text.lower()
        w = f" {t} "

        # Fullscreen -----------------------------------------------------
        if "fullscreen" in t or "full screen" in t:
            return [
                LLMToolCall("browser_fullscreen"),
                "I've toggled fullscreen on the video. Enjoy!",
            ]

        # Play a specific result (e.g. "Play the second video") ----------
        if "second video" in t or ("play the" in t and "video" in t):
            idx = 1 if "second" in t else 0
            return [
                LLMToolCall("browser_click", {"selector": "video", "index": idx}),
                "Playing that video now.",
            ]

        # "Search X on YouTube" / "Search Iron Man" ----------------------
        if "search" in t:
            query = "iron man" if "iron man" in t else t.replace("search", "").replace("for", "").replace("on youtube", "").replace("youtube", "").replace("google", "").strip()
            if not query:
                query = "great music"
            q = query.replace(" ", "+")
            if "youtube" in t or "iron man" in t:
                url = f"https://www.youtube.com/results?search_query={q}"
                label = "YouTube"
            else:
                url = f"https://www.google.com/search?q={q}"
                label = "the web"
            return [
                LLMToolCall("open_url", {"url": url}),
                f"I've searched {label} for '{query}'.",
            ]

        # YouTube / video / song pipelines (multi-step open -> search -> play -> fullscreen)
        if any(k in t for k in ("youtube", "lofi", "song", "music", "video", "iron man")):
            query = ""
            if "beats" in t or "lofi" in t:
                query = "lofi chill focus beats"
            elif "iron man" in t:
                query = "iron man"
            elif "relax" in t:
                query = "relaxing music"
            else:
                query = "great music"
            q = query.replace(" ", "+")
            # "Open YouTube" (no play intent) -> just open.
            if "play" not in t and "song" not in t and "music" not in t and "video" not in t:
                return [
                    LLMToolCall("open_url", {"url": "https://www.youtube.com"}),
                    "I've opened YouTube for you.",
                ]
            return [
                LLMToolCall("open_url", {"url": "https://www.youtube.com"}),
                LLMToolCall(
                    "open_url",
                    {"url": f"https://www.youtube.com/results?search_query={q}"},
                ),
                LLMToolCall("browser_click", {"selector": "video", "index": 0}),
                LLMToolCall("browser_key", {"key": "f"}),
                f"I've opened YouTube, searched for '{query}' and started the video in fullscreen. Enjoy!",
            ]

        # WhatsApp / message ----------------------------------------------
        if any(k in t for k in ("whatsapp", "message", "send a message")):
            return [
                LLMToolCall("browser_navigate", {"url": "https://web.whatsapp.com"}),
                "I've opened WhatsApp Web for you. You can now pick your chat and type your message — I'll be ready for the next command.",
            ]

        # File system -----------------------------------------------------
        if any(k in t for k in ("delete", "remove", "clear cache", "rm ")):
            path = "/home/user/Projects/cache.txt"
            if "tmp" in t or "cache" in t:
                path = "/home/user/Projects/temp_cache.txt"
            return [
                LLMToolCall("delete_file", {"path": path}),
                f"I've deleted the file at {path}.",
            ]
        if any(k in t for k in ("create a folder", "make a folder", "create folder", "new folder")):
            import datetime
            name = "PLUTO"
            for part in ["pluto_v2", "pluto", "projects"]:
                if part in t:
                    name = part
                    break
            path = f"/home/user/Projects/{name.upper()}"
            return [
                LLMToolCall("create_directory", {"path": path}),
                LLMToolCall(
                    "create_file",
                    {"path": f"{path}/README.md", "content": f"# {name}\nCreated on {datetime.date.today()}."},
                ),
                f"Created the folder {path} and added a README inside it.",
            ]
        if any(k in t for k in ("create a file", "make a file", "create file")):
            name = "hello.txt"
            if "test" in t:
                name = "test.txt"
            path = f"/home/user/Projects/{name}"
            return [
                LLMToolCall("create_file", {"path": path, "content": "Hello from PLUTO!\n"}),
                f"Created a file at {path}.",
            ]

        # System / stats --------------------------------------------------
        if any(k in t for k in ("system", "cpu", "ram", "memory", "process", "status", "stats", "optimize")):
            return [
                LLMToolCall("get_processes", {"limit": 10}),
                "I've checked your system. CPU and memory look healthy, and the top running processes are now displayed on your activity panel.",
            ]

        # Applications ----------------------------------------------------
        apps = {
            "vscode": "Visual Studio Code", "code": "Visual Studio Code",
            "firefox": "Firefox", "browser": "Firefox",
            "terminal": "Terminal", "calculator": "Calculator",
            "settings": "Settings", "spotify": "Spotify", "vlc": "VLC",
        }
        for key, label in apps.items():
            if key in t and "open" in t:
                alias = "code" if key in ("vscode", "code") else key
                return [
                    LLMToolCall("open_application", {"application": alias}),
                    f"I've opened {label} for you.",
                ]

        # Open URL / web search -------------------------------------------
        if "open " in t and ("url" in t or "http" in t):
            import re
            m = re.search(r"https?://\S+", t)
            url = m.group(0) if m else "https://www.google.com"
            return [LLMToolCall("open_url", {"url": url}), f"I've opened {url}."]
        if "search" in t or "google" in t:
            query = t.replace("search", "").replace("google", "").replace("for", "").strip()
            q = query.replace(" ", "+") or "open+source"
            return [
                LLMToolCall("open_url", {"url": f"https://www.google.com/search?q={q}"}),
                f"I've searched the web for '{query}' and opened the results.",
            ]

        # Plain conversation / greeting -----------------------------------
        if any(g in t for g in ("hello", "hi", "hey", "who are you", "what can you do", "help")):
            return [
                "Hello! I'm PLUTO, your Linux desktop assistant. I can open apps, manage files, "
                "control the browser, check system stats and run multi-step tasks — just speak or type a command."
            ]

        return [
            f"Understood. I can handle that — '{user_text}'. Tell me what you'd like to do next, "
            "for example 'Open YouTube and play a song' or 'Create a folder called PLUTO in my Projects directory'."
        ]


# Singleton instance
gpt_oss_client = GPTOSSClient()
