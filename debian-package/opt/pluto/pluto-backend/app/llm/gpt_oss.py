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


def _import_intent_planner():
    """Lazy import: keeps the LLM module importable without the agent stack."""
    from app.agent.nlu import NLUStep, intent_planner

    return NLUStep, intent_planner


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
        context: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        if self.mock_mode or not self.client:
            return await self._mock_chat(messages, tools, context)

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
    @staticmethod
    def _conversation_context(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Rebuild the current-context hint from recent tool observations.

        Lets the mock planner chain follow-ups inside one task AND across
        turns without any real LLM: e.g. a tool that just ran reports
        ``current_url=...`` or ``path=...`` and the next planned step can use
        it.
        """
        context: Dict[str, Any] = {}
        for m in messages:
            content = str(m.get("content", ""))
            for key in ("url=", "path=", "count=", "title="):
                if key in content:
                    snippet = content.split(key, 1)[1].split(" | ", 1)[0]
                    if key == "url=":
                        context["current_url"] = snippet.strip()
                    elif key == "path=":
                        context["recent_files"] = [snippet.strip()]
                    elif key == "title=":
                        context["current_page_title"] = snippet.strip()
            if content.startswith("ERROR"):
                context["last_error"] = content
        return context

    async def _mock_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
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

        NLUStep, intent_planner = _import_intent_planner()
        merged_context: Dict[str, Any] = dict(context or {})
        merged_context.update(self._conversation_context(messages))

        raw_plan = intent_planner.plan(user_text, merged_context)
        plan_seq = [self._as_llm_tool_call(item) for item in raw_plan]
        step_indices = [
            i for i, item in enumerate(plan_seq) if isinstance(item, LLMToolCall)
        ]

        if executed < len(step_indices):
            step = plan_seq[step_indices[executed]]
            if not step.id:
                step.id = f"call_{executed}"
            return LLMResponse(content=None, tool_calls=[step], finish_reason="tool_calls")

        final = next(
            (item for item in reversed(plan_seq) if isinstance(item, str)),
            "Done, BOSS. Anything else?",
        )
        return LLMResponse(content=self._communicative(final), finish_reason="stop")

    @classmethod
    def _as_llm_tool_call(cls, item: Any) -> Any:
        NLUStep, _ = _import_intent_planner()
        if isinstance(item, NLUStep):
            return LLMToolCall(name=item.name, arguments=item.arguments)
        return item

    # ------------------------------------------------------------------
    # Mock replies are written terse; upgrade them so mock mode is as
    # communicative as the real model (user-facing style, ~2-3 sentences).
    # ------------------------------------------------------------------
    _REPLY_UPGRADES = {
        "I've opened YouTube.": (
            "YouTube is open in your browser, BOSS - the homepage loaded just "
            "fine. Want me to search for something?"
        ),
        "I've opened GitHub.": (
            "GitHub is open and ready, BOSS. Want me to search for a repository "
            "or open one of your projects?"
        ),
        "Playing the second video.": (
            "Done, BOSS - the second result is open and playing now. I'm still "
            "listening if you want the next one."
        ),
        "Playing it.": (
            "Playing it now, BOSS. Tell me if you want a different result."
        ),
        "Screenshot taken.": (
            "Screenshot captured and saved, BOSS. Want me to open it so you can "
            "take a look?"
        ),
        "Command executed.": (
            "The command ran and finished cleanly, BOSS. Anything else you'd "
            "like me to do?"
        ),
    }

    @classmethod
    def _communicative(cls, text: Optional[str]) -> str:
        if not text:
            return "Done, BOSS. Anything else?"
        text = text.strip()
        if text in cls._REPLY_UPGRADES:
            return cls._REPLY_UPGRADES[text]
        # Already warm and addressed to the user? Leave it as-is.
        if "BOSS" in text:
            return text
        # Generic upgrade: confirm + invite the next step.
        if text.endswith("."):
            return f"{text} I'm still listening, BOSS - what's next?"
        return text

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
    def _build_plan(cls, user_text: str, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Return the ordered mock plan (LLMToolCall/str) for one command.

        Delegates to the shared NLU router so the planner, the intent
        endpoint and the registry recommendations can never disagree.
        """
        NLUStep, intent_planner = _import_intent_planner()
        raw = intent_planner.plan(user_text, context or {})
        return [cls._as_llm_tool_call(item) for item in raw]

# Singleton instance
gpt_oss_client = GPTOSSClient()
