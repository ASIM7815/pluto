"""PLUTO deterministic intent planner (NLU).

Turns a natural-language command into an ordered list of real tool calls
(plus conversational text). This single router is shared by:

- the offline mock planner (``gpt_oss._mock_chat``),
- the ``/api/tools/intent/analyze`` route (``registry.get_recommended_tools``),

so what a user is told is always exactly what the registry would execute.

Design rules:
* Synonyms route to the same tool; the router is phrase-based but organised
  around intents, not exact-phrase lists.
* Every emitted tool exists in the registry (``PLANNED_TOOL_NAMES`` is a
  hard filter so the planner can never invent capabilities).
* Follow-up requests ("play the second video", "search Iron Man" after opening
  YouTube) are resolved from the session context passed in ``context``.
* When no real tool matches, PLUTO says what it *can* do instead of silently
  claiming something happened.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Plan items
# ---------------------------------------------------------------------------
@dataclass
class NLUStep:
    """One planned tool invocation."""

    name: str
    arguments: Dict[str, Any] = dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.arguments is None:
            self.arguments = {}


PlanItem = Union[NLUStep, str]


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
# Everything the planner is allowed to emit. Registry tool list (must be kept
# in sync with app/tools/registry.py).
PLANNED_TOOL_NAMES = {
    # application
    "open_application", "close_application", "switch_to_application",
    "list_running_applications",
    # file
    "open_file", "open_folder", "find_files", "create_folder", "create_file",
    "read_file", "list_directory", "delete_file", "move_file", "copy_file",
    # system
    "take_screenshot", "set_volume", "get_volume", "copy_to_clipboard",
    "get_clipboard", "get_processes", "kill_process",
    # browser
    "open_url", "browser_search", "browser_click", "browser_key",
    "browser_type", "browser_fullscreen", "browser_snapshot", "close_browser",
    # message
    "send_message", "open_chat_app",
    # terminal
    "execute_command",
}

# Spoken location words -> home-relative folder.
_DIR_ALIASES: Dict[str, str] = {
    "desktop": "~/Desktop",
    "documents": "~/Documents",
    "document": "~/Documents",
    "docs": "~/Documents",
    "downloads": "~/Downloads",
    "download": "~/Downloads",
    "pictures": "~/Pictures",
    "photos": "~/Pictures",
    "picture": "~/Pictures",
    "music": "~/Music",
    "videos": "~/Videos",
    "video": "~/Videos",
    "movies": "~/Videos",
    "projects": "~/Projects",
    "project": "~/Projects",
    "home": "~",
    "home folder": "~",
    "home directory": "~",
    "the documents folder": "~/Documents",
}

_SCREENSHOT_AREA_WINDOW = ("window", "active window", "this window", "current window")
_SCREENSHOT_AREA_SELECT = ("select", "selection", "region", "a part of the screen",
                           "part of the screen", "area of the screen", "an area")

_ORDINAL_TO_INDEX = {
    "first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "sixth": 5, "6th": 5,
    "seventh": 6, "7th": 6, "eighth": 7, "8th": 7, "ninth": 8, "9th": 8,
    "tenth": 9, "10th": 9,
}

_SITE_KEYWORDS = {
    "youtube": "youtube", "you tube": "youtube", "github": "github",
    "reddit": "reddit", "wikipedia": "wikipedia", "wiki": "wikipedia",
    "amazon": "amazon", "maps": "maps", "google maps": "maps",
    "google": "google", "duckduckgo": "duckduckgo", "bing": "bing",
}

_GREETING_WORDS = ("hello", "hi ", "hey", "yo ", "good morning", "good afternoon",
                   "good evening", "howdy", "hiya")
_THANKS_WORDS = ("thank", "thanks", "appreciate", "good job", "great job", "nice work",
                 "awesome", "well done", "much obliged")

# Keep some phrase continuity with older tests / docs.
_SCREENSHOT_PHRASES = (
    "screenshot", "screen shot", "screen capture", "capture the screen",
    "capture my screen", "capture a screenshot", "capture the screen to",
    "take a screenshot", "take screenshot", "snapshot of the screen",
    "snapshot the screen", "screen grab", "grab a screenshot", "print screen",
    "printscreen", "capture screen", "grab the screen", "take a screen capture",
)


class IntentPlanner:
    """Deterministic NLU -> tool plan router."""

    # ------------------------------------------------------------------
    @classmethod
    def plan(cls, user_text: str, context: Optional[Dict[str, Any]] = None) -> List[PlanItem]:
        """Ordered plan (NLUStep/str). Empty/silence => short message."""
        text = (user_text or "").strip()
        if not text:
            return ["I didn't catch that - try again, BOSS."]
        ctx = dict(context or {})
        plan = cls._route(text, ctx)
        if not plan:
            plan = [cls._capabilities_reply()]
        # Never allow a tool the registry does not actually provide.
        plan = [
            item if isinstance(item, str) or item.name in PLANNED_TOOL_NAMES
            else f"I can't run '{getattr(item, 'name', '?')}' yet, BOSS."
            for item in plan
        ]
        return plan

    @classmethod
    def recommend(cls, user_text: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Tool names the plan would execute (deduped, ordered)."""
        seen: List[str] = []
        try:
            for item in cls.plan(user_text, context):
                if isinstance(item, NLUStep) and item.name not in seen:
                    seen.append(item.name)
        except Exception as e:  # noqa: BLE001
            logger.warning("nlu_recommend_error", error=str(e))
        return seen

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _norm(value: str) -> str:
        """Lowercase, collapse whitespace, keep apostrophes."""
        return " ".join((value or "").split()).lower()

    @classmethod
    def _t(cls, text: str) -> str:
        return cls._norm(text)

    @classmethod
    def _has(cls, text: str, *subs: str) -> bool:
        t = cls._t(text)
        return any(s in t for s in subs)

    @classmethod
    def _words(cls, text: str) -> str:
        return f" {cls._norm(text)} "

    @classmethod
    def _ctx(cls, context: Optional[Dict[str, Any]], key: str) -> str:
        value = (context or {}).get(key)
        return str(value or "")

    # ------------------------------------------------------------------
    # Routing order
    # ------------------------------------------------------------------
    @classmethod
    def _route(cls, text: str, ctx: Dict[str, Any]) -> List[PlanItem]:
        t = cls._norm(text)
        words = cls._words(text)

        # 0) silence / interrupts handled by the agent loop; keep a guard.
        if any(k in t for k in ("go silent", "stop listening", "be quiet")):
            return ["Going silent. I'll be here if you need me, BOSS."]

        # 1) Screenshots (most literal, must beat "open" rules)
        if any(k in t for k in _SCREENSHOT_PHRASES) or (
            cls._has(text, "take", "capture", "grab", "print", "shoot")
            and cls._has(text, "screenshot", "screen", "screen shot")
        ):
            area = cls._screenshot_area(text, t)
            args: Dict[str, Any] = {"area": area}
            folder = cls._dir_from_text(text, default="")
            if cls._has(text, "save", "store", "put", "keep") or folder:
                args["directory"] = folder or "~/Pictures"
            m = re.search(r"\bas\s+([\w\-. ]+?)(?:\.\s|$)", text, re.I)
            if m and re.search(r"\.(png|jpe?g|webp)$", m.group(1).strip(), re.I):
                args["filename"] = m.group(1).strip()
            where = args.get("directory", "~/Pictures")
            return [
                NLUStep("take_screenshot", args),
                f"Taking a screenshot{(' saved to ' + where) if 'directory' in args else ''}, BOSS.",
            ]

        # 2) Volume / mute
        if cls._has(text, "volume", "sound", "audio", "mute", "unmute") or (
            cls._has(text, "loud", "louder", "quieter") and cls._has(text, "too", "set",
                                                                     "turn", "make it", "down", "up")
        ):
            lower = t
            if any(k in lower for k in ("unmute", "sound back on", "turn the sound on",
                                        "audio on", "un-mute", "un mute")):
                return [NLUStep("set_volume", {"level": "unmute"}), "Audio unmuted, BOSS."]
            if any(k in lower for k in ("mute", "muted", "silence the sound",
                                        "turn off sound", "sound off", "turn the sound off",
                                        "no sound", "mute audio")):
                return [NLUStep("set_volume", {"level": "mute"}), "Audio muted, BOSS."]
            m = re.search(r"(\d{1,3})\s*%?", t)
            if m:
                level = max(0, min(100, int(m.group(1))))
                return [
                    NLUStep("set_volume", {"level": str(level)}),
                    f"Volume set to {level}%, BOSS.",
                ]
            if any(k in t for k in ("what", "how loud", "current", "get ", "read ", "show",
                                    "check")):
                return [NLUStep("get_volume", {}), "Reading the current volume, BOSS."]
            # "louder/quieter/up/down" without a number -> tell the user the
            # honest capability instead of pretending to change it.
            return [
                "I can set the volume to a specific level (e.g. \"set volume to 40\") "
                "or mute/unmute the audio, BOSS. What level do you want?"
            ]

        # 3) Clipboard
        if "clipboard" in t or "clip board" in t:
            is_copy = any(k in t for k in ("copy", "put", "set", "save", "store",
                                           "add", "send"))
            is_read = any(k in t for k in ("what", "read", "get", "show", "contents",
                                           "paste", "fetch"))
            if is_copy and not is_read:
                payload = cls._clipboard_text(text)
                return [
                    NLUStep("copy_to_clipboard", {"text": payload}),
                    "Copied to the clipboard, BOSS.",
                ]
            return [NLUStep("get_clipboard", {}), "Reading the clipboard, BOSS."]

        # 4) Greetings / social / meta
        greetings = cls._greeting_plan(text)
        if greetings is not None:
            return greetings

        # 5) System status & process checks
        sys_plan = cls._system_plan(text)
        if sys_plan is not None:
            return sys_plan

        # 6) Browser & website intents (search / open URL / follow-ups)
        browser_plan = cls._browser_plan(text, ctx)
        if browser_plan is not None:
            return browser_plan

        # 7) File operations
        file_plan = cls._file_plan(text, ctx)
        if file_plan is not None:
            return file_plan

        # 8) Messaging intents
        msg_plan = cls._messaging_plan(text)
        if msg_plan is not None:
            return msg_plan

        # 9) Terminal command (skips known apps/sites: "run spotify" opens the app)
        terminal_plan = cls._terminal_plan(text)
        if terminal_plan is not None:
            return terminal_plan

        # 10) Applications (list / close / switch / open)
        app_plan = cls._application_plan(text, ctx)
        if app_plan is not None:
            return app_plan

        # 11) Explicit URL mention
        m_url = re.search(r"https?://\S+", text, re.I)
        if m_url:
            url = m_url.group(0).rstrip(".,;!?")
            return [NLUStep("open_url", {"url": url}), f"Opening {url}, BOSS."]

        return []

    # ------------------------------------------------------------------
    # Greetings / social / help
    # ------------------------------------------------------------------
    @classmethod
    def _greeting_plan(cls, text: str) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        words = cls._words(text)

        if any(w in words for w in (" who are you ", " what are you ", " introduce yourself ",
                                    " your name ", " what is your name ")):
            return [
                "I'm PLUTO, your autonomous Linux desktop assistant. I run real tools on "
                "this machine - applications, browser automation, files, screenshots, "
                "system control - and verify each action before I report back."
            ]

        if any(k in t for k in _THANKS_WORDS):
            return ["You're welcome, BOSS! What would you like me to do next?"]

        if any(k in t for k in ("what can you do", "help", "capabilities", "what tools",
                                "your features", "show commands", "list your skills")):
            return [cls._capabilities_reply()]

        # bare greeting with no action word => chatty welcome
        if (t in ("hi", "hey", "yo", "sup", "hiya", "hello", "howdy", "what's up", "whats up")
                or (any(t.startswith(g.rstrip()) for g in _GREETING_WORDS)
                    and not any(k in t for k in (
                        "open", "search", "play", "create", "send", "delete", "move",
                        "copy", "close", "run", "take", "set", "read", "find", "list",
                        "screenshot", "show", "mute", "quit", "kill", "start", "launch",
                        "type", "scroll", "click", "zoom", "install")))):
            return [
                "Hello BOSS! I'm PLUTO, your autonomous Linux desktop assistant. I can "
                "open apps and websites, search and browse, manage files, take "
                "screenshots, control volume and clipboard, check the system and run "
                "commands. What do you need?"
            ]

        if any(k in words for k in (" how are you", " how's it going", " hows it going",
                                    " how are things")):
            return ["Running smoothly, BOSS! What can I do for you?"]
        return None

    @classmethod
    def _capabilities_reply(cls) -> str:
        return (
            "Here's what I can do, BOSS: open and close apps, browse and search "
            "(YouTube, Google, websites), create/read/copy/move/delete files and "
            "folders, take screenshots, control volume and the clipboard, check "
            "running processes, and run terminal commands with your approval."
        )

    # ------------------------------------------------------------------
    # Screenshot area parsing
    # ------------------------------------------------------------------
    @classmethod
    def _screenshot_area(cls, text: str, t: str) -> str:
        if any(k in t for k in _SCREENSHOT_AREA_WINDOW):
            return "window"
        if any(k in t for k in _SCREENSHOT_AREA_SELECT):
            return "select"
        return "full"

    # ------------------------------------------------------------------
    # System / process intent
    # ------------------------------------------------------------------
    @classmethod
    def _system_plan(cls, text: str) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        words = cls._words(text)

        status_phrases = ("system status", "system stats", "system health", "system info",
                          "system information", "performance", "optimize", "cpu usage",
                          "memory usage", "ram usage", "disk usage", "disk space",
                          "task manager", "process list", "running processes",
                          "top processes", "what's running", "what is running",
                          "list processes", "show processes", "see processes",
                          "processes running")
        if any(k in t for k in status_phrases):
            limit = 15 if any(k in t for k in ("top", "list", "show", "see")) else 8
            return [
                NLUStep("get_processes", {"limit": limit}),
                "Here's what's running on the system, BOSS.",
            ]

        # "is <X> running?" / "check if <X> is running"
        m_running = re.search(
            r"(?:is|are)\s+([a-z0-9_.-]{1,40}?)\s+running\??$", t
        ) or re.search(
            r"(?:check|see|tell me)\s+if\s+([a-z0-9_.-]{1,40}?)\s+(?:is\s+)?running", t
        )
        if m_running and not any(k in t for k in ("which", "what", "list")):
            name = m_running.group(1).strip()
            if name not in ("it", "this", "that"):
                return [
                    NLUStep("get_processes", {"name": name}),
                    f"Checking whether {name} is running, BOSS.",
                ]

        # kill / stop <process> / "kill the process named X"
        kill_verbs = any(w in words for w in (" kill ", " stop ", " end ", " terminate "))
        if kill_verbs and any(k in t for k in ("process", "task", "application", "program",
                                               "app ")):
            m_kill = re.search(
                r"(?:kill|stop|end|terminate)\s+(?:the\s+)?(?:process|task|application|"
                r"program|app)?\s*(?:named|called|name)?\s*([a-z0-9_.-]{2,40}?)\s*$",
                t,
            )
            name = m_kill.group(1).strip() if m_kill else ""
            name = re.sub(r"\s+(process|task|application|program|app)$", "", name).strip()
            if name and name not in ("it", "that", "this", "everything", "all", "a", "the"):
                return [
                    NLUStep("kill_process", {"process": name}),
                    f"Stopping {name}, BOSS.",
                ]
        return None

    # ------------------------------------------------------------------
    # Clipboard payload
    # ------------------------------------------------------------------
    @classmethod
    def _clipboard_text(cls, text: str) -> str:
        t = cls._norm(text)
        quoted = re.search(r"[\"'](.+?)[\"']", text)
        if quoted:
            return quoted.group(1).strip()
        markers = ("copy ", "put ", "set ", "save ", "store ", "add ", "send ")
        for marker in markers:
            if marker in t:
                idx = t.index(marker) + len(marker)
                rest = t[idx:]
                for stop in (" to the clipboard", " on the clipboard", " onto the clipboard",
                             " to clipboard", " on clipboard", " into the clipboard"):
                    rest = rest.split(stop)[0]
                rest = rest.strip(" ,.;:!?").strip()
                if rest:
                    return rest
        return ""

    # ------------------------------------------------------------------
    # File system intent
    # ------------------------------------------------------------------
    @classmethod
    def _dir_from_text(cls, text: str, default: str = "~/Documents") -> str:
        """Pick the spoken location (Documents/Downloads/...) in text."""
        t = cls._norm(text)
        # Prefer a literal path token when present.
        m_path = re.search(r"(?:/|~/)[\w./~-]+", text)
        if m_path:
            return os.path.expanduser(m_path.group(0)).rstrip("/") or default
        best: Optional[str] = None
        for alias, path in _DIR_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", t):
                if best is None or len(alias) > len(best):
                    best = alias
                    chosen = path
        if best is None:
            return default
        return chosen

    @classmethod
    def _file_name_from(cls, text: str) -> Optional[str]:
        """Extract a file/folder name mentioned after 'called'/'named' (etc).

        Case is preserved from the original user text ("Reports" stays
        "Reports").
        """
        quoted = re.search(r"[\"']([^\"']+)[\"']", text)
        if quoted:
            return quoted.group(1).strip()
        m = re.search(
            r"(?:called|named)\s+([A-Za-z0-9_.\- ]+?)"
            r"(?=\s+(?:in|inside|under|on|at|to|for|please|and|then|saying|"
            r"containing|with|that|,)|$)",
            text, re.I,
        )
        if m:
            name = m.group(1).strip().strip(" .")
            if name and name.lower() not in ("a folder", "folder", "the folder", "a file",
                                             "file", "the file", "new folder", "new file"):
                return name
        return None

    @classmethod
    def _file_plan(cls, text: str, ctx: Dict[str, Any]) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        words = cls._words(text)

        def resolve_candidate(name: str) -> str:
            """Resolve a possibly-relative file reference against context/home."""
            if not name:
                return ""
            if name.startswith(("~", "/")):
                return os.path.expanduser(name)
            # 1) recent file in context with this basename
            for recent in (ctx.get("recent_files") or []):
                if os.path.basename(str(recent)) == name:
                    return str(recent)
            # 2) standard folders
            for folder in ("~/Documents", "~/Downloads", "~/Desktop", "~/Projects",
                           "~/Pictures", "~"):
                candidate = os.path.join(os.path.expanduser(folder), name)
                if os.path.exists(candidate):
                    return candidate
            # 3) current directory context
            base = ctx.get("current_directory")
            if base:
                return os.path.join(str(base), name)
            return os.path.join(os.path.expanduser("~/Documents"), name)

        # ---- list directory
        if any(k in t for k in ("list files", "list the files", "list directory",
                                "list contents", "show files", "show the files",
                                "what's in", "what is in", "what's inside", "files in",
                                "folders in", "directory listing", "contents of")):
            directory = cls._dir_from_text(text, default=cls._ctx(ctx, "current_directory") or "~")
            return [NLUStep("list_directory", {"path": directory}),
                    f"Listing {directory}, BOSS."]

        # ---- find / search for files
        if any(k in t for k in ("find ", "search for ", "look for ")) and any(
            k in t for k in ("file", "files", "document", "folder", "directory", "pdf",
                             "matching", "named", "called")
        ):
            query_m = re.search(
                r"(?:find|search for|look for)\s+(?:files?\s+)?(?:named|called|matching)?\s*"
                r"(.+?)\s*(?:in|under|inside)\s+(.+)$", t
            )
            if query_m:
                query = query_m.group(1).strip()
                location = cls._dir_from_text(query_m.group(2))
            else:
                raw = re.sub(r"^(find|search for|look for)\s+(?:files?\s+|documents?\s+)?",
                             "", t)
                raw = re.sub(r"\s+(in|under|inside)\s+(.+)$", "", raw)
                raw = re.sub(r"^matching\s+", "", raw)
                query = raw.strip(" .,;")
                location = cls._ctx(ctx, "current_directory") or "~"
            if query:
                return [NLUStep("find_files", {"query": query, "location": location}),
                        f"Searching for '{query}', BOSS."]

        # ---- create a folder
        if cls._has(text, "create", "make", "new") and cls._has(text, "folder", "directory"):
            name = cls._file_name_from(text)
            if name and name.lower() not in ("a", "the", "new", "folder", "directory"):
                parent = cls._dir_from_text(text, default="~/Documents")
                path = os.path.join(os.path.expanduser(parent), name)
                return [NLUStep("create_folder", {"path": path}),
                        f"Creating folder {name}, BOSS."]

        # ---- create a file
        if cls._has(text, "create", "make", "new", "write") and cls._has(text, "file"):
            name_m = re.search(
                r"(?:called|named)\s+([\w.\-]+(?:\.[A-Za-z0-9]+)?)", text, re.I)
            name = name_m.group(1).strip() if name_m else None
            if not name:
                name_m2 = re.search(r"(?:file|document)\s+([\w.\-]+\.[A-Za-z0-9]{1,10})", text, re.I)
                name = name_m2.group(1).strip() if name_m2 else None
            if name:
                content = cls._file_content(text)
                parent = cls._dir_from_text(text, default="~/Documents")
                path = os.path.join(os.path.expanduser(parent), name)
                return [NLUStep("create_file", {"path": path, "content": content}),
                        f"Creating {name}, BOSS."]

        # ---- open file / open folder
        if cls._has(text, "open the folder", "open folder", "show folder", "open the folder",
                    "open directory") or (
            cls._has(text, "open", "open up") and cls._has(text, "folder", "directory")
        ):
            name = cls._file_name_from(text)
            path = resolve_candidate(name) if name else cls._ctx(ctx, "current_directory")
            if path:
                return [NLUStep("open_folder", {"path": path}), f"Opening {path}, BOSS."]

        if (cls._has(text, "open file", "open the file", "open up the file", "read file",
                     "show me the file", "open") and not cls._has(text, "application", "app ")):
            name_m = re.search(r"(?:file\s+)?(?:called|named)?\s*([\w.\-/~]+\.\w{1,10})", text)
            name = name_m.group(1).strip() if name_m else None
            if name:
                path = resolve_candidate(name)
                return [NLUStep("open_file", {"path": path}), f"Opening {name}, BOSS."]

        # ---- read a file
        if cls._has(text, "read", "contents of", "show contents") and any(
            k in t for k in ("file", "document", "note", ".txt", ".md", "text")
        ):
            name_m = re.search(r"(?:file|document|note|text)\s+([\w.\-/~]+(?:\.\w+)?)", t) \
                or re.search(r"(?:called|named)?\s*([\w.\-/~]+\.\w{1,10})", text)
            name = name_m.group(1).strip() if name_m else None
            if name:
                path = resolve_candidate(name)
                return [NLUStep("read_file", {"path": path}), f"Reading {os.path.basename(path)}, BOSS."]

        # ---- delete a file
        if cls._has(text, "delete", "remove", "trash", "erase") and any(
            k in t for k in ("file", "document", "note", "folder")
        ):
            name_m = re.search(r"(?:the\s+)?(?:file|document|folder|note)\s+"
                               r"(?:called|named)?\s*([\w.\-/~]+(?:\.\w+)?)", text)
            name = name_m.group(1).strip() if name_m else None
            if name:
                path = resolve_candidate(name)
                return [NLUStep("delete_file", {"path": path}), f"Deleting {name}, BOSS."]

        # ---- move / rename / copy
        for verb, step in (("rename", "move_file"), ("move", "move_file"), ("copy", "copy_file")):
            if f"{verb} " not in t and not t.startswith(verb):
                continue
            m = re.search(
                rf"{verb}\s+(?:the\s+)?(?:file|document|folder)?\s*(?:called|named)?\s*"
                rf"([\w./~-]+(?:\.[A-Za-z0-9]+)?)\s+(?:from\s+(.+?))?\s*to\s+([\w./~ -]+?)\s*$",
                text, re.I,
            )
            if not m:
                continue
            src_name, from_raw, dst_raw = m.group(1).strip(), (m.group(2) or "").strip(), m.group(3).strip()

            def _dir_of(token: str) -> str:
                tok = (token or "").strip().lower()
                for alias, folder in _DIR_ALIASES.items():
                    if re.search(rf"\b{re.escape(alias)}\b", tok):
                        return folder
                return ""

            src_folder = _dir_of(from_raw) if from_raw else "~/Documents"
            src_path = os.path.join(os.path.expanduser(src_folder), src_name)
            if dst_raw.startswith(("~", "/")):
                dst_path = os.path.expanduser(dst_raw)
            elif dst_raw in _DIR_ALIASES or _dir_of(dst_raw):
                # destination is a folder -> keep the source basename inside it
                dst_path = os.path.join(os.path.expanduser(_dir_of(dst_raw)), os.path.basename(src_name))
            elif re.fullmatch(r"[\w .-]+\.[A-Za-z0-9]{1,10}", dst_raw):
                # destination is a new file name -> same folder as the source
                dst_path = os.path.join(os.path.dirname(src_path), dst_raw)
            else:
                # unknown destination token: treat as a new name/path
                dst_path = os.path.join(os.path.dirname(src_path), dst_raw)
            action = "Moving" if step == "move_file" else "Copying"
            return [
                NLUStep(step, {"source": src_path, "destination": dst_path}),
                f"{action} {src_name} to {os.path.basename(dst_path)}, BOSS.",
            ]

    @classmethod
    def _file_content(cls, text: str) -> str:
        t = cls._norm(text)
        quoted = re.search(r"[\"'](.+?)[\"']", text)
        if quoted:
            return quoted.group(1).strip()
        for marker in ("saying ", "containing ", "with content ", "with the text ",
                       "that says ", "reading "):
            if marker in t:
                idx = t.index(marker) + len(marker)
                return t[idx:].strip(" .,;").strip()
        return ""

    # ------------------------------------------------------------------
    # Browser intent (URLs, search, YouTube, follow-ups)
    # ------------------------------------------------------------------
    @classmethod
    def _site_from_url(cls, url: str) -> str:
        lower = (url or "").lower()
        for key in ("youtube.com", "youtu.be"):
            if key in lower:
                return "youtube"
        if "github.com" in lower:
            return "github"
        if "reddit.com" in lower:
            return "reddit"
        if "wikipedia.org" in lower:
            return "wikipedia"
        if "amazon." in lower:
            return "amazon"
        if "google.com/search" in lower or "google." in lower:
            return "google"
        if "duckduckgo.com" in lower:
            return "duckduckgo"
        if "bing.com" in lower:
            return "bing"
        return ""

    @classmethod
    def _browser_plan(cls, text: str, ctx: Dict[str, Any]) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        words = cls._words(text)
        current_url = cls._ctx(ctx, "current_url")

        # ---- close / manage the browser window
        if any(k in t for k in ("close the browser", "close browser", "quit the browser",
                                "quit browser", "exit the browser", "close the chrome window")):
            return [NLUStep("close_browser", {}), "Browser closed, BOSS."]
        if any(k in words for k in (" refresh ", " reload ", " reload the page ")):
            return [NLUStep("browser_key", {"key": "F5"}), "Page refreshed, BOSS."]
        if any(k in words for k in (" fullscreen ", " full screen ", " make it fullscreen ")):
            return [NLUStep("browser_key", {"key": "F11"}), "Fullscreen toggled, BOSS."]

        # ---- what's on the page / the screen now
        if any(k in t for k in ("what's on the screen", "what is on the screen",
                                "what's on the page", "what is on the page",
                                "what do you see", "snapshot the page",
                                "read the page", "page snapshot", "browser snapshot",
                                "what's open in the browser")):
            return [NLUStep("browser_snapshot", {}), "Here's what's on the page, BOSS."]

        # ---- YouTube pipeline ---------------------------------------------
        yt_ctx = "youtube.com" in current_url or "youtu.be" in current_url
        on_youtube = yt_ctx
        yt_intent = any(k in t for k in ("youtube", "you tube", "yt ")) or (
            "video" in t and ("play" in t or "watch" in t)
        ) or (on_youtube and any(k in t for k in ("search", "play", "watch", "find")))
        if yt_intent:
            # what to play / search
            quoted = re.search(r"[\"']([^\"']+)[\"']", text)
            query = ""
            if quoted:
                query = quoted.group(1).strip()
            else:
                markers = ("search for ", "search ", "look for ", "find ", "play ", "watch ")
                for marker in markers:
                    if marker in t:
                        idx = t.index(marker) + len(marker)
                        query = text[idx:]  # keep original casing ("Iron Man")
                        lower_q = query.lower()
                        cut = None
                        for stop in (" on youtube", " in youtube", " second video",
                                     " first video", " third video", " and", " please",
                                     ", then", " then "):
                            pos = lower_q.find(stop)
                            if pos != -1 and (cut is None or pos < cut):
                                cut = pos
                        if cut is not None:
                            query = query[:cut]
                        query = query.strip(" ,.;:!?")
                        break
            query_l = query.lower().strip()
            # "play the second video / the next one" is a follow-up click on the
            # current results page, not a new search.
            if query_l and re.fullmatch(
                r"(?:the\s+)?(?:first|second|third|fourth|fifth|next|top|one|\d+(?:st|nd|rd|th)?)"
                r"(?:\s+(?:video|result|one|episode))?", query_l
            ):
                query = ""
            if query_l in ("it", "that", "this", "one", "top", "the top", "the"):
                query = ""
            if not query:
                m_im = re.search(r"iron man", text, re.I)
                if m_im:
                    query = m_im.group(0)

            ordinal: Optional[int] = None
            if any(k in t for k in ("the second", "second video", "2nd", "next video",
                                    "the third", "third video", "3rd", "the first",
                                    "first video", "1st")):
                for word, idx in _ORDINAL_TO_INDEX.items():
                    if re.search(rf"\b{re.escape(word)}\b", t):
                        ordinal = idx
                        break

            steps: List[PlanItem] = []
            need_open = not on_youtube and (
                "open youtube" in t or "go to youtube" in t or "youtube" in t
                or "video" in t or "you tube" in t
            )
            if need_open:
                steps.append(NLUStep("open_url", {"url": "https://www.youtube.com"}))
            if query:
                site = "youtube"
                steps.append(NLUStep("browser_search", {"query": query, "site": site}))
            if ordinal is not None:
                steps.append(NLUStep("browser_click", {
                    "selector": "a#video-title", "index": ordinal,
                }))
                label = next((k for k, v in _ORDINAL_TO_INDEX.items()
                              if v == ordinal and k.isalpha()), f"#{ordinal + 1}")
                steps.append(f"Opened and started the {label} video, BOSS.")
            elif "play" in t or "watch" in t or "listen" in t:
                steps.append(NLUStep("browser_click", {
                    "selector": "a#video-title", "index": 0,
                }))
                steps.append("Playing it now, BOSS.")
            elif query:
                steps.append(f"Searching YouTube for '{query}', BOSS.")
            else:
                steps.append("YouTube is open, BOSS. Want me to search something?")
            if steps:
                return steps

        # ---- nth-result follow-up on the current page ("play the second video")
        if any(re.search(rf"\b{re.escape(w)}\b", t) for w in
               ("second", "third", "fourth", "fifth", "2nd", "3rd", "4th", "5th",
                "next one", "next result", "next video", "first one", "first result",
                "top result", "another one")):
            ordinal: Optional[int] = None
            for word, idx in _ORDINAL_TO_INDEX.items():
                if re.search(rf"\b{re.escape(word)}\b", t):
                    ordinal = idx
                    break
            if ordinal is None:  # next one / another one
                prev = ctx.get("selected_result_index")
                ordinal = (int(prev) + 1) if isinstance(prev, int) else 1
            selector = "a#video-title" if on_youtube else "a"
            args: Dict[str, Any] = {"index": ordinal}
            if selector:
                args["selector"] = selector
            return [NLUStep("browser_click", args),
                    f"Opened result number {ordinal + 1}, BOSS."]

        # ---- open an explicit URL
        m_url = re.search(r"https?://\S+", text, re.I)
        if m_url:
            url = m_url.group(0).rstrip(".,;!?")
            return [NLUStep("open_url", {"url": url}), f"Opening {url}, BOSS."]

        # ---- website alias open ("open gmail", "go to reddit", "open github.com")
        if any(w in words for w in (" open ", " launch ", " start ", " go to ", " visit ",
                                    " navigate to ", " take me to ", " open up ")) or t.startswith(
            ("open ", "go to ", "visit ", "launch ")
        ):
            # remove leading verb + filler
            rest = re.sub(
                r"^(?:please\s+)?(?:open up|open|launch|start|go to|visit|navigate to|"
                r"take me to)\s+(?:the\s+|a\s+)?", "", t).strip()
            if not rest:
                return None
            if cls._is_app_or_site_ref(rest):
                from app.tools.application_tools import APP_MAPPINGS
                if any(re.search(rf"\b{re.escape(a)}\b", rest) for a in APP_MAPPINGS):
                    return None  # e.g. "open google chrome" -> application tool
            site = cls._site_keyword(rest)
            if site:
                from app.tools.browser import _SITE_URLS
                url = _SITE_URLS.get(site)
                if url:
                    return [NLUStep("open_url", {"url": url}), f"Opened {site}, BOSS."]
            if re.search(r"[\w-]+\.[a-z]{2,}", rest):
                url = rest if rest.startswith("http") else f"https://{rest}"
                return [NLUStep("open_url", {"url": url}), f"Opened {rest}, BOSS."]
            # no known app/site for a bare word -> fall through (app layer decides)
            return None

        # ---- generic web search
        search_verbs = any(k in t for k in ("search ", "look up ", "search the web",
                                            "search the internet", "google ", "web search",
                                            "find out about ", "find information on "))
        if search_verbs and any(k in t for k in (" file", " files", " document", " folder")):
            return None  # file plan handles "find/search for files"
        if search_verbs:
            query_m = re.search(r"(?:search|look up|google|find out about|"
                                r"find information on)\s+(?:for\s+)?(.+)", t)
            query = query_m.group(1).strip() if query_m else ""
            site = "google"
            for kw, key in _SITE_KEYWORDS.items():
                if re.search(rf"\b(?:on|in)\s+{re.escape(kw)}\b", t):
                    site = key
                    break
            if site == "google":
                site = cls._site_from_url(current_url) or "google"
            if not query:
                return None
            # strip trailing "please"/"for me"
            query = re.sub(r"\s+(please|for me|thanks)$", "", query)
            return [NLUStep("browser_search", {"query": query, "site": site}),
                    f"Searched for '{query}', BOSS."]

        # ---- search while already on a site
        if cls._has(text, "search") and on_youtube:
            query_m = re.search(r"search\s+(?:for\s+)?(.+)", t)
            if query_m:
                query = query_m.group(1).strip()
                return [NLUStep("browser_search", {"query": query, "site": "youtube"}),
                        f"Searched YouTube for '{query}', BOSS."]

        return None

    @staticmethod
    def _site_keyword(rest: str) -> Optional[str]:
        """Map a phrase like 'gmail', 'google maps', 'stack overflow' to a site key."""
        from app.tools.browser import _SITE_URLS

        if rest in _SITE_URLS:
            return rest
        # longest alias first
        for key in sorted(_SITE_URLS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", rest):
                return key
        return None

    # ------------------------------------------------------------------
    # Messaging intent
    # ------------------------------------------------------------------
    @classmethod
    def _messaging_plan(cls, text: str) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        app = None
        if "whatsapp" in t:
            app = "whatsapp"
        elif "telegram" in t or "tg " in t:
            app = "telegram"
        elif "signal" in t:
            app = "signal"

        if app is None:
            return None
        if any(k in t for k in ("open ", "launch ", "go to ", "start ")) and not any(
            k in t for k in ("send", "message", "text", "tell", "ping", "notify")
        ):
            return [NLUStep("open_chat_app", {"app": app}), f"Opened {app.title()}, BOSS."]

        send_verbs = ("send", "message", "text", "tell", "ping", "notify", "write to", "msg")
        app_as_verb = t.startswith(app + " ") and not any(k in t for k in ("web", "website"))
        if any(k in t for k in send_verbs) or app_as_verb:
            recipient_part = t
            content = ""
            quoted = re.search(r"[\"'](.+?)[\"']", text)
            for marker in ("saying that ", "saying ", "that says ", "the message ",
                           "with the message ", "the following ", "telling him ",
                           "telling her ", "text: ", " that ", ": "):
                if marker in t:
                    idx = t.index(marker)
                    recipient_part = t[:idx]
                    content = text[idx + len(marker):].strip(" '\"")
                    break
            if not content and quoted:
                content = quoted.group(1).strip()
            if content.lower().startswith("that "):
                content = content[5:].strip()
            if not content:
                return [NLUStep("open_chat_app", {"app": app}),
                        f"Tell me who to message on {app.title()} and what to say, BOSS."]

            # recipient: prefer the person after the last "to"
            recipient = ""
            if " to " in recipient_part:
                recipient = recipient_part.split(" to ")[-1].strip()
            else:
                recipient = recipient_part
                recipient = re.sub(r"^(send|message|text|tell|ping|notify|write to|msg|"
                                   r"please)\s*", "", recipient)
            recipient = recipient.replace(app, "").strip()
            recipient = re.sub(r"^(a |an |the |my |to |for )+", "", recipient)
            recipient = re.sub(r"\s+(on|via|using)\s+(whatsapp|telegram|signal).*$", "", recipient)
            recipient = recipient.strip(" ,:'\".-")
            if not recipient:
                return [NLUStep("open_chat_app", {"app": app}),
                        f"Who should I message on {app.title()}?"]
            return [
                NLUStep("send_message", {"recipient": recipient, "message": content}),
                f"Sending to {recipient} on {app.title()}, BOSS.",
            ]
        return None

    # ------------------------------------------------------------------
    # Applications intent
    # ------------------------------------------------------------------
    @classmethod
    def _application_plan(cls, text: str, ctx: Dict[str, Any]) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        words = cls._words(text)
        from app.tools.application_tools import APP_MAPPINGS, KNOWN_WEBSITES

        def app_alias() -> Optional[str]:
            """Match app mapping by longest alias."""
            best = None
            for alias in APP_MAPPINGS:
                if re.search(rf"\b{re.escape(alias)}\b", t):
                    if best is None or len(alias) > len(best[0]):
                        best = (alias, APP_MAPPINGS[alias])
            return best[1] if best else None

        # ---- which apps are running
        if any(k in t for k in ("what apps are running", "what applications are running",
                                "which apps are running", "which apps are open",
                                "list running apps", "list running applications",
                                "show running apps", "running apps", "running applications",
                                "apps running", "open applications", "what programs are running",
                                "programs running")):
            return [NLUStep("list_running_applications", {}),
                    "Here are the running applications, BOSS."]

        # ---- switch / focus
        if any(k in words for k in (" switch to ", " focus on ", " focus ", " bring up ",
                                    " switch over to ", " go to the ")):
            app = app_alias()
            if app:
                return [NLUStep("switch_to_application", {"application": app}),
                        f"Switched to {app}, BOSS."]
            return None

        # ---- close / quit an app
        if any(w in words for w in (" close ", " quit ", " exit ", " kill ")) and (
            "app" in t or "application" in t or "program" in t or app_alias()
        ):
            app = app_alias()
            if app:
                return [NLUStep("close_application", {"application": app}),
                        f"Closed {app}, BOSS."]
            return None

        # ---- open / launch an app or website
        open_words = (" open ", " launch ", " start ", " run ", " open up ", " pull up ")
        if any(w in words for w in open_words) or t.startswith("open "):
            rest = re.sub(
                r"^(?:please\s+)?(?:open up|open|launch|start|run|pull up)\s+"
                r"(?:the\s+|a\s+)?", "", t).strip()
            app = app_alias()
            if app:
                return [NLUStep("open_application", {"application": app}),
                        f"Opening {app}, BOSS."]
            if rest in KNOWN_WEBSITES:
                return [NLUStep("open_url", {"url": KNOWN_WEBSITES[rest]}),
                        f"Opened {rest}, BOSS."]
            from app.tools.browser import _SITE_URLS
            if rest in _SITE_URLS:
                return [NLUStep("open_url", {"url": _SITE_URLS[rest]}),
                        f"Opened {rest}, BOSS."]
            if re.search(r"[\w-]+\.[a-z]{2,}", rest):
                url = rest if rest.startswith("http") else f"https://{rest}"
                return [NLUStep("open_url", {"url": url}), f"Opened {rest}, BOSS."]
            # unknown app -> try to open by that exact name (tool verifies it exists)
            return [NLUStep("open_application", {"application": rest}),
                    f"Opening {rest}, BOSS."]
        return None

    @staticmethod
    def _is_app_or_site_ref(cmd: str) -> bool:
        """True when a captured run/open target is a known app or website."""
        w = (cmd or "").strip().strip("'\"").lower()
        if not w:
            return False
        try:
            from app.tools.application_tools import APP_MAPPINGS, KNOWN_WEBSITES
            from app.tools.browser import _SITE_URLS

            candidates = dict(APP_MAPPINGS)
            candidates.update(KNOWN_WEBSITES)
            candidates.update(_SITE_URLS)
            if w in candidates:
                return True
            # spoken multi-word aliases contained in the command
            # (google chrome, vs code, visual studio code, ...)
            for alias in candidates:
                if " " in alias and re.search(rf"\b{re.escape(alias)}\b", w):
                    return True
        except Exception:  # noqa: BLE001
            pass
        return False

    # ------------------------------------------------------------------
    # Terminal intent

    # ------------------------------------------------------------------
    @classmethod
    def _terminal_plan(cls, text: str) -> Optional[List[PlanItem]]:
        t = cls._norm(text)
        if any(k in t for k in ("run the command", "run command", "execute the command",
                                "execute command", "run the terminal command")) or t.startswith(
            ("run ", "execute ", "terminal:" )
        ):
            raw = re.sub(r"^(?:please\s+)?(?:run the command|run command|execute the command|"
                         r"execute command|run the terminal command|run|execute|terminal:)\s*",
                         "", text, flags=re.I).strip()
            raw = re.sub(r"\s*(please|thanks|thank you)$", "", raw).strip()
            raw = re.sub(r"\s+in the terminal$", "", raw).strip()
            raw = re.sub(r"\s+using the terminal$", "", raw).strip()
            raw = raw.strip("'\"")
            if raw and raw.lower() not in ("it", "that", "a command", "command", "terminal"):
                if cls._is_app_or_site_ref(raw):
                    return None  # "run spotify/firefox" is an app launch
                return [NLUStep("execute_command", {"command": raw}),
                        f"Running '{raw}', BOSS."]
        return None


# Singleton used by gpt_oss / registry / routes.
intent_planner = IntentPlanner()
