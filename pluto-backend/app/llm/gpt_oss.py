"""GPT-OSS 120B LLM client (OpenAI-compatible).

- Real mode (GPT_OSS_API_KEY set): calls the configured OpenAI-compatible
  endpoint (default: Groq) with proper auth, timeout, tools and parsing.
- Mock mode (no key): a deterministic intent->tool planner so the whole
  Listen -> ... -> Speak -> Listen loop can still be exercised locally.
  The mock planner ONLY plans - every tool it proposes is executed for real by
  the registry, so failures are still honest failures.
"""
from __future__ import annotations

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
    error: Optional[str] = None


class GPTOSSClient:
    """Client for GPT-OSS 120B via an OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        self.api_key = settings.gpt_oss_api_key
        self.base_url = settings.gpt_oss_base_url.rstrip("/")
        self.model = settings.gpt_oss_model
        self.mock_mode = settings.pluto_llm_mock_mode
        self.client: Optional[httpx.AsyncClient] = None
        if not self.mock_mode:
            if not self.api_key:
                logger.warning("llm_key_missing_falling_back_to_mock")
                self.mock_mode = True
            else:
                self.client = httpx.AsyncClient(
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=90.0,
                )

    # ------------------------------------------------------------------
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        if self.mock_mode or not self.client:
            return await self._mock_chat(messages, tools)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.pluto_llm_temperature,
            "max_tokens": max_tokens or settings.pluto_llm_max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            logger.info("gpt_oss_request", model=self.model, message_count=len(messages))
            response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            return self._normalise(response.json())
        except httpx.HTTPStatusError as e:
            body = ""
            try:
                body = e.response.text[:400]
            except Exception:  # noqa: BLE001
                pass
            # Some providers reject "max_tokens" for reasoning models; retry once
            # with max_completion_tokens.
            if e.response.status_code == 400 and "max_tokens" in body.lower():
                try:
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
                    retry = await self.client.post(
                        f"{self.base_url}/chat/completions", json=payload
                    )
                    retry.raise_for_status()
                    return self._normalise(retry.json())
                except Exception as e2:  # noqa: BLE001
                    logger.error("gpt_oss_retry_error", error=str(e2))
                    return LLMResponse(finish_reason="error", error=f"AI request failed: {e2}")
            logger.error("gpt_oss_http_error", status=e.response.status_code, body=body)
            return LLMResponse(
                finish_reason="error",
                error=f"The AI service returned an error (HTTP {e.response.status_code}).",
            )
        except httpx.HTTPError as e:
            logger.error("gpt_oss_error", error=str(e))
            return LLMResponse(
                finish_reason="error",
                error="I could not reach the AI service. Please check your connection and the GPT_OSS_API_KEY.",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("gpt_oss_parse_error", error=str(e))
            return LLMResponse(
                finish_reason="error",
                error="The AI service returned an unreadable response.",
            )

    @staticmethod
    def _normalise(data: Dict[str, Any]) -> LLMResponse:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Malformed LLM response: {e}") from e
        message = choice.get("message", {}) or {}
        finish_reason = choice.get("finish_reason")

        content = message.get("content")
        tool_calls: List[LLMToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {}) or {}
            args_raw = fn.get("arguments", "{}")
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw) if args_raw.strip() else {}
                except json.JSONDecodeError:
                    args = {"_parse_error": args_raw[:200]}
            elif isinstance(args_raw, dict):
                args = args_raw
            else:
                args = {}
            if not isinstance(args, dict):
                args = {}
            tool_calls.append(
                LLMToolCall(name=fn.get("name", ""), arguments=args, id=tc.get("id", ""))
            )

        logger.info(
            "gpt_oss_response", finish_reason=finish_reason, tool_calls=len(tool_calls)
        )
        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason=finish_reason)

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None

    # ------------------------------------------------------------------
    # Mock planner (used only when no API key is configured)
    # ------------------------------------------------------------------
    async def _mock_chat(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]
    ) -> LLMResponse:
        user_text = ""
        last_user_idx = -1
        for i, m in enumerate(messages):
            if m.get("role") == "user":
                user_text = str(m.get("content", ""))
                last_user_idx = i

        executed = sum(
            1 for m in messages[last_user_idx + 1:] if m.get("role") == "tool"
        )

        plan = self._build_plan(user_text)
        plan_seq = list(plan)
        if executed < len(plan_seq):
            step = plan_seq[executed]
            if isinstance(step, LLMToolCall):
                if not step.id:
                    step.id = f"call_{executed}"
                return LLMResponse(content=None, tool_calls=[step], finish_reason="tool_calls")
            return LLMResponse(content=step, finish_reason="stop")
        return LLMResponse(
            content=plan_seq[-1] if plan_seq else "Done. Anything else?",
            finish_reason="stop",
        )

    # ------------------------------------------------------------------
    # Deterministic intent parsing for mock mode. Uses ONLY tools that exist
    # in the unified registry. Multi-step plans are executed sequentially and
    # stop at the first real failure (the orchestrator reports it) - PLUTO
    # never continues on top of a failed step.
    # ------------------------------------------------------------------
    @staticmethod
    def _strip_noise(text: str, words_to_remove: List[str]) -> str:
        out = text
        for w in words_to_remove:
            out = out.replace(w, " ")
        return " ".join(out.split()).strip(" '\",.!?")

    @classmethod
    def _extract_youtube_query(cls, user_text: str) -> Optional[str]:
        t = user_text.lower()
        # Explicit quoted search.
        if '"' in user_text:
            inside = user_text.split('"')
            if len(inside) >= 2 and inside[1].strip():
                return inside[1].strip()
        if "iron man" in t:
            return "iron man"
        if "interstellar" in t:
            return "interstellar"
        if "lofi" in t or "chill" in t or "beats" in t:
            return "lofi chill focus beats"
        if "relax" in t or "calm" in t:
            return "relaxing music"
        if "song" in t or "music" in t or "video" in t or "play" in t:
            # Try to find a quoted title or known phrase after "play".
            for marker in ("play ", "play the ", "play me "):
                if marker in user_text:
                    rest = user_text.split(marker, 1)[1]
                    rest = cls._strip_noise(rest, ["on youtube", "youtube", "please", "the", "a song", "song", "music", "video", "some"])
                    if rest and len(rest) < 40:
                        return rest
        return None

    @classmethod
    def _build_plan(cls, user_text: str) -> List[Any]:
        t = user_text.lower()
        words = f" {t} "

        def search(site: str, query: str) -> LLMToolCall:
            return LLMToolCall("browser_search", {"query": query, "site": site})

        # ---- silence / stop ---------------------------------------------
        if any(k in t for k in ("silence", "stop listening", "be quiet", "shut up", "go silent")):
            return ["Going silent. I'll be here if you need me."]

        # ---- plain conversation ------------------------------------------
        if any(k in words for k in (
            " hello ", " hi ", " hey ", " who are you", " what can you do",
            " how are you", " thanks", " thank you", " good morning", " good evening",
        )):
            return [
                "Hello! I'm PLUTO, your autonomous Linux desktop assistant. "
                "I can open apps and websites, search the web, manage files, control "
                "the browser and check your system - just tell me what you need."
            ]
        if "?" in user_text and not any(k in t for k in (
            "open", "search", "play", "create", "send", "delete", "move", "copy", "choose", "click"
        )):
            return [
                "I understand the question. If it's about this computer, try 'check system "
                "status', or ask me to open an app or website."
            ]

        # ---- web / youtube pipeline --------------------------------------
        is_youtube_task = "youtube" in t or "iron man" in t and any(
            k in t for k in ("play", "search", "video", "watch", "open")
        )
        if is_youtube_task:
            open_yt = "open youtube" in t or ("youtube" in t and ("open" in t or "go to" in t or "launch" in t))
            want_search = any(k in t for k in ("search", "find ")) and "second video" not in t and "then" not in t
            query = cls._extract_youtube_query(user_text)

            if any(k in t for k in ("second video", "third video", "2nd video", "second result")):
                idx = 1
                steps: List[Any] = []
                if "open youtube" in t or open_yt:
                    steps.append(LLMToolCall("open_url", {"url": "https://www.youtube.com"}))
                if query:
                    steps.append(search("youtube", query))
                steps.append(LLMToolCall("browser_click", {"selector": "a#video-title", "index": idx}))
                steps.append("Playing the second video.")
                return steps

            if open_yt and not want_search and query:
                # "Open YouTube and play Iron Man"
                return [
                    LLMToolCall("open_url", {"url": "https://www.youtube.com"}),
                    search("youtube", query),
                    LLMToolCall("browser_click", {"selector": "a#video-title", "index": 0}),
                    f"I've opened YouTube, searched for '{query}' and started the first result.",
                ]
            if open_yt and not want_search:
                return [LLMToolCall("open_url", {"url": "https://www.youtube.com"}), "I've opened YouTube."]
            if want_search or query:
                q = query or "music"
                return [
                    LLMToolCall("open_url", {"url": "https://www.youtube.com"}),
                    search("youtube", q),
                    f"I've opened YouTube and searched for '{q}'.",
                ]

        # Search a specific site (google / web)
        if any(k in t for k in ("search ", "google", "look up", "find ")) and not any(
            k in t for k in ("youtube", "video", "song")
        ):
            q = cls._strip_noise(user_text, ["please", "search", "google", "the web", "on the web", "for", "look up", "find", "web"])
            q = q or "open source"
            return [search("google", q), f"I've searched the web for '{q}'."]

        # Explicit URL
        if "http://" in t or "https://" in t:
            import re
            m = re.search(r"https?://\S+", t)
            if m:
                url = m.group(0).rstrip(".,;!?")
                return [LLMToolCall("open_url", {"url": url}), f"I've opened {url}."]

        # Follow-up: choose Nth result on the current page ------------------
        for idx_key, idx in (("second", 1), ("third", 2), ("first", 0), ("fourth", 3)):
            if f"{idx_key} video" in t or f"{idx_key} result" in t or f"{idx_key} one" in t:
                return [
                    LLMToolCall("browser_click", {"selector": "a#video-title", "index": idx}),
                    f"Opening the {idx_key} result.",
                ]
        if any(k in t for k in ("play the video", "play video", "play it", "click it")):
            return [LLMToolCall("browser_click", {"selector": "a#video-title", "index": 0}), "Playing it."]

        # Website aliases ----------------------------------------------------
        site_aliases = {
            "gmail": ("https://mail.google.com", "Gmail"),
            "google": ("https://www.google.com", "Google"),
            "google maps": ("https://maps.google.com", "Google Maps"),
            "maps": ("https://maps.google.com", "Google Maps"),
            "reddit": ("https://www.reddit.com", "Reddit"),
            "github": ("https://github.com", "GitHub"),
            "x": ("https://x.com", "X"),
            "twitter": ("https://x.com", "X"),
            "linkedin": ("https://www.linkedin.com", "LinkedIn"),
            "netflix": ("https://www.netflix.com", "Netflix"),
            "wikipedia": ("https://www.wikipedia.org", "Wikipedia"),
            "amazon": ("https://www.amazon.com", "Amazon"),
            "whatsapp web": ("https://web.whatsapp.com", "WhatsApp Web"),
            "whatsapp": ("https://web.whatsapp.com", "WhatsApp Web"),
            "telegram": ("https://web.telegram.org", "Telegram Web"),
            "duckduckgo": ("https://duckduckgo.com", "DuckDuckGo"),
        }
        for key, (url, label) in site_aliases.items():
            if f"open {key}" in t or f"go to {key}" in t or f"open the {key}" in t:
                return [LLMToolCall("open_url", {"url": url}), f"I've opened {label}."]

        # Messaging -------------------------------------------------------------
        if any(k in t for k in ("whatsapp", "telegram")) and any(
            k in t for k in ("send", "message", "tell", "text")
        ):
            import re as _re
            m = _re.search(
                r"(?:send|message|text|tell)\s+([A-Za-z0-9_. ]+?)\s+(?:saying|that|this)\s+",
                user_text, _re.I,
            )
            recipient = (m.group(1).strip() if m else None)
            text = ""
            for marker in ("saying", "that ", "this message", "text "):
                if marker in user_text:
                    text = user_text.split(marker, 1)[1].strip(" '\"")
                    break
            if not recipient or not text:
                app = "whatsapp" if "whatsapp" in t else "telegram"
                return [
                    LLMToolCall("open_chat_app", {"app": app}),
                    f"I've opened {'WhatsApp' if 'whatsapp' in t else 'Telegram'} - tell me who to message and what to say.",
                ]
            return [
                LLMToolCall("send_message", {"recipient": recipient, "message": text}),
                f"Message sent to {recipient}.",
            ]

        # Filesystem -----------------------------------------------------------
        if any(k in t for k in ("create a folder", "make a folder", "create folder", "new folder", "make a directory", "create directory", "create a directory")):
            path = "/home/user/Projects/PLUTO"
            import re as _re
            named = _re.search(r"(?:folder|directory)\s*(?:called|named)?\s*[`']?([A-Za-z0-9_-]+)", user_text)
            if named and named.group(1).lower() not in ("a", "the", "new", "my", "inside", "in"):
                path = f"/home/user/Projects/{named.group(1).upper()}"
            return [LLMToolCall("create_folder", {"path": path}), f"Created the folder {path}."]
        if any(k in t for k in ("create a file", "make a file", "create file", "new file", "write a file")):
            return [LLMToolCall("create_file", {"path": "/home/user/Projects/pluto-note.txt", "content": "Created by PLUTO.\n"}), "Created /home/user/Projects/pluto-note.txt."]
        if "delete" in t and any(k in t for k in ("file", "folder", "cache", "trash", "tmp")):
            return [LLMToolCall("delete_file", {"path": "/home/user/Projects/pluto-note.txt"}), "Deleted the file."]
        if ("find " in t or "locate " in t) and ("file" in t or "document" in t):
            return [LLMToolCall("find_files", {"query": "pluto"}), "Here is what I found."]
        if ("open " in t or "launch " in t) and "file" in t and "app" not in t:
            return [LLMToolCall("open_file", {"path": "/home/user/Projects/pluto-note.txt"}), "Opened the file."]
        if ("open folder" in t or "open directory" in t or "open files" in t or "open my files" in t):
            return [LLMToolCall("open_folder", {"path": "/home/user/Projects"}), "Opened the folder."]
        if "open " in t and ("folder" in t or "directory" in t or "path" in t):
            rest = t.split("open", 1)[1].replace("the", "").replace("folder", "").replace("directory", "").replace("at", "").replace("path", "").strip()
            if rest.startswith("/") or rest.startswith("~"):
                return [LLMToolCall("open_folder", {"path": rest}), "Opened the folder."]

        # Applications ------------------------------------------------------------
        apps = {
            "vscode": "code", "vs code": "code", "visual studio code": "code", "code": "code",
            "firefox": "firefox", "browser": "firefox", "chrome": "google-chrome",
            "terminal": "gnome-terminal", "console": "gnome-terminal",
            "calculator": "gnome-calculator", "settings": "gnome-control-center",
            "spotify": "spotify", "vlc": "vlc", "discord": "discord", "slack": "slack",
            "gimp": "gimp", "files": "nautilus", "file manager": "nautilus",
            "libreoffice": "libreoffice",
        }
        for key, exe in apps.items():
            if key in t and ("open " in t or "launch " in t or "start " in t or "run " in t):
                return [LLMToolCall("open_application", {"application": exe}), f"Opening {key.title()}."]
        if "open " in t:
            rest = cls._strip_noise(t, ["open", "please", "the", "an", "a", "app", "application", "program"])
            if rest:
                return [LLMToolCall("open_application", {"application": rest}), f"Opening {rest}."]

        # System -------------------------------------------------------------------
        if any(k in t for k in ("system status", "system stats", "check system", "cpu", "memory", "ram", "processes", "optimize", "performance", "what's running")):
            return [LLMToolCall("get_processes", {"limit": 8}), "Here are the top processes on your system."]
        if "screenshot" in t or "capture the screen" in t:
            return [LLMToolCall("take_screenshot", {}), "Screenshot taken."]
        if any(k in t for k in ("volume", "mute", "unmute", "sound")):
            if "mute" in t and "unmute" not in t:
                return [LLMToolCall("set_volume", {"level": "mute"}), "Audio muted."]
            if "unmute" in t:
                return [LLMToolCall("set_volume", {"level": "unmute"}), "Audio unmuted."]
            return [LLMToolCall("get_volume", {}), "Here is the current volume."]
        if "copy" in t and "clipboard" in t:
            text = cls._strip_noise(t, ["copy", "this", "to", "the", "clipboard", "please"])
            return [LLMToolCall("copy_to_clipboard", {"text": text or "clipboard"}), "Copied to the clipboard."]
        if "run " in t and ("command" in t or "terminal" in t):
            cmd = cls._strip_noise(t, ["run", "this", "command", "the", "in", "terminal", "please", "following"])
            if cmd:
                return [LLMToolCall("execute_command", {"command": cmd}), "Command executed."]

        # Fallback ------------------------------------------------------------------
        return [
            f"Understood - '{user_text[:160]}'. On your desktop I can open apps and websites, "
            "search (e.g. YouTube), manage files, and check system stats. "
            "Tell me which of those you'd like."
        ]


# Singleton instance
gpt_oss_client = GPTOSSClient()
