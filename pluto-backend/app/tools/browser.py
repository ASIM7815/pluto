"""PLUTO Browser Automation.

PLUTO controls a real Chromium instance through Playwright when it is
installed (``pip install playwright`` + ``python -m playwright install
chromium``). Every action is real: navigating genuinely loads a page, clicking
clicks a real element, snapshots read the live DOM. When Playwright or a
browser binary is unavailable the tools return an honest error with an install
hint - PLUTO never fabricates a page or a click.

All access is serialised through an asyncio lock so voice input, API calls and
concurrent sessions cannot corrupt each other's page state. The single shared
browser matches the desktop-assistant model (one visible PLUTO browser window).
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.tools.terminal_base import (
    TerminalTool,
    ToolResult,
    SafetyLevel,
    has_display,
)

logger = get_logger(__name__)

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout  # type: ignore
    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # noqa: BLE001
    _PLAYWRIGHT_AVAILABLE = False

_MISSING_HINT = (
    "Browser automation is not installed. Run: pip install playwright && "
    "python -m playwright install chromium"
)

# Real browsers installed on the machine, most-preferred first. PLUTO drives
# the USER'S browser when one is found instead of Playwright's bundled copy,
# so "open YouTube" opens in the Chrome you actually use (with your PLUTO
# profile), not a random anonymous Chromium window.
_BROWSER_CANDIDATES = [
    ("google-chrome-stable", "Google Chrome"),
    ("google-chrome", "Google Chrome"),
    ("chrome", "Google Chrome"),
    ("/usr/bin/google-chrome-stable", "Google Chrome"),
    ("/usr/bin/google-chrome", "Google Chrome"),
    ("/opt/google/chrome/chrome", "Google Chrome"),
    ("chromium-browser", "Chromium"),
    ("chromium", "Chromium"),
    ("/snap/bin/chromium", "Chromium"),
    ("brave-browser", "Brave"),
    ("microsoft-edge", "Microsoft Edge"),
    ("vivaldi-stable", "Vivaldi"),
]

_SEARCH_ENGINES = {
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "google": "https://www.google.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "reddit": "https://www.reddit.com/search/?q={q}",
    "github": "https://github.com/search?q={q}&type=repositories",
    "amazon": "https://www.amazon.com/s?k={q}",
    "maps": "https://www.google.com/maps/search/{q}",
}

# Spoken site names -> home URLs so "open youtube" / "youtube.com" all work.
_SITE_URLS = {
    "youtube": "https://www.youtube.com",
    "yt": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "chatgpt": "https://chat.openai.com",
    "openai": "https://openai.com",
    "linkedin": "https://www.linkedin.com",
    "maps": "https://maps.google.com",
    "duckduckgo": "https://duckduckgo.com",
    "whatsapp": "https://web.whatsapp.com",
}

# Text fragments Chrome/Chromium render on a failed navigation.
_NAV_ERROR_MARKERS = (
    "net::err",
    "this site can’t be reached",
    "this site can't be reached",
    "err_name_not_resolved",
    "err_connection_refused",
    "err_connection_reset",
    "err_internet_disconnected",
    "err_timed_out",
    "server not found",
    "page isn’t working",
    "hmm… we’re having trouble",
)


def _is_unlikely_blank(url: str) -> bool:
    return bool(url and url not in ("about:blank", ""))


def detect_system_browser() -> Optional[Tuple[str, str]]:
    """Find the user's real installed Chromium-family browser.

    Returns (executable_path, display_name) or None when nothing is installed.
    Firefox & co. cannot be driven through Playwright's chromium API, so they
    are deliberately NOT candidates here.
    """
    import shutil

    for candidate, name in _BROWSER_CANDIDATES:
        if candidate.startswith("/"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate, name
            continue
        found = shutil.which(candidate)
        if found:
            return found, name
    return None


def normalize_url(raw: str) -> str:
    """Turn 'youtube', 'youtube.com' or 'Open YouTube' style input into a
    loadable URL; unknown bare words fall back to a Google search."""
    value = (raw or "").strip().strip("\"'")
    if not value:
        return "https://www.google.com"
    key = value.lower().removeprefix("https://").removeprefix("http://").rstrip("/")

    if "://" in value:
        return value
    # Known spoken site names (with or without .com)
    if key in _SITE_URLS:
        return _SITE_URLS[key]
    if key.endswith(".com") and key[:-4] in _SITE_URLS:
        return _SITE_URLS[key[:-4]]
    if key.startswith("www.") and key[4:] in _SITE_URLS:
        return _SITE_URLS[key[4:]]
    if key.endswith(".com") and key.startswith("www."):
        return f"https://{key}"
    if "." in key and " " not in key:
        # Looks like a domain (github.io, wikipedia.org, ...)
        return f"https://{key}"
    # Anything else (spaces, single words) -> search the web for it.
    import urllib.parse

    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(value)


class BrowserManager:
    """Lazy Playwright browser with a lock-serialised active page.

    Resolution order for the browser binary:
      1. ``PLUTO_BROWSER_EXECUTABLE`` env var (explicit override)
      2. ``pluto_browser_executable`` setting (explicit override)
      3. The user's REAL installed browser (google-chrome / chromium / ...)
      4. Playwright's bundled Chromium (requires ``playwright install chromium``)

    When a real profile-capable launch is used, PLUTO keeps a persistent
    profile under ``~/.pluto/browser-profile`` so logins survive between runs.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pw = None
        self._browser = None      # classic launch (non-persistent)
        self._context = None      # persistent-context launch
        self._page = None
        self.browser_name: str = "not started"

    @property
    def available(self) -> bool:
        return _PLAYWRIGHT_AVAILABLE

    async def _is_browser_alive(self) -> bool:
        """Check if browser/context and page are still alive and usable."""
        if not self._page:
            return False
        try:
            if self._browser is not None and not self._browser.is_connected():
                return False
            # Accessing a live property raises once the page/context is gone.
            _ = self._page.url
            return True
        except Exception:  # noqa: BLE001
            return False

    def _resolve_launch_target(self) -> Dict[str, Any]:
        """Decide which browser binary to use. Returns launch kwargs."""
        headless = settings.pluto_browser_headless
        if headless == "auto":
            headless = not has_display()

        kwargs: Dict[str, Any] = {"headless": bool(headless)}
        executable = (
            os.environ.get("PLUTO_BROWSER_EXECUTABLE", "").strip()
            or settings.pluto_browser_executable.strip()
        )
        if executable:
            kwargs["executable_path"] = executable
            self.browser_name = os.path.basename(executable).title()
            return kwargs

        detected = detect_system_browser()
        if detected is not None:
            path, name = detected
            kwargs["executable_path"] = path
            self.browser_name = name
            return kwargs

        # No system browser: Playwright's bundled Chromium.
        self.browser_name = "Chromium (Playwright bundled)"
        if settings.pluto_browser_channel.strip():
            kwargs["channel"] = settings.pluto_browser_channel.strip()
        return kwargs

    async def _ensure(self) -> ToolResult:
        if not _PLAYWRIGHT_AVAILABLE:
            return ToolResult.fail("browser", _MISSING_HINT, error_code="MISSING_DEPENDENCY")

        # Reuse the live browser when possible.
        if self._page and await self._is_browser_alive():
            return ToolResult.ok("browser", "ready")
        logger.info("browser_closed_detected", action="reopening")
        await self._close_unlocked()

        try:
            self._pw = await async_playwright().start()
            launch_kwargs = self._resolve_launch_target()

            if settings.pluto_browser_persistent_profile:
                profile_dir = os.path.expanduser(settings.pluto_browser_profile_dir)
                os.makedirs(profile_dir, exist_ok=True)
                # no_viewport => the page fills the real OS window (headful).
                self._context = await self._pw.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    args=[
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-crash-reporter",
                    ],
                    no_viewport=not launch_kwargs["headless"],
                    **launch_kwargs,
                )
                pages = getattr(self._context, "pages", None) or []
                self._page = pages[0] if pages else await self._context.new_page()
            else:
                self._browser = await self._pw.chromium.launch(**launch_kwargs)
                self._page = await self._browser.new_page()

            logger.info(
                "browser_started",
                browser=self.browser_name,
                headless=bool(launch_kwargs.get("headless")),
                persistent=bool(settings.pluto_browser_persistent_profile),
            )
            return ToolResult.ok(
                "browser",
                f"started ({self.browser_name})",
                data={"browser": self.browser_name},
            )
        except Exception as e:  # noqa: BLE001
            logger.error("browser_start_error", error=str(e), browser=self.browser_name)
            await self._close_unlocked()
            # Give an actionable hint depending on what we tried to launch.
            hint = (
                f"PLUTO could not start {self.browser_name}: {e}. "
                "Set PLUTO_BROWSER_EXECUTABLE to your browser's path (e.g. "
                "/usr/bin/google-chrome) or install one: "
                "sudo apt-get install google-chrome-stable chromium-browser. "
                f"Alternatively {_MISSING_HINT}"
            )
            return ToolResult.fail("browser", hint, error_code="BROWSER_START_FAILED")

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()

    async def _close_unlocked(self) -> None:
        """Release browser resources. Caller must already hold ``_lock``."""
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    await closer.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = None
        self._browser = None
        self._page = None
        self._pw = None

    # ------------------------------------------------------------------
    async def _read_page_snippet(self) -> str:
        """A short text sample of the page body (for error-page detection)."""
        try:
            return await self._page.evaluate(
                "() => document.body ? document.body.innerText.slice(0, 1500) : ''"
            )
        except Exception:  # noqa: BLE001
            return ""

    async def _looks_like_error_page(self, title: str, body: str) -> Optional[str]:
        haystack = f"{title}\n{body}".lower()
        for marker in _NAV_ERROR_MARKERS:
            if marker in haystack:
                return marker
        return None

    async def _goto(self, url: str) -> ToolResult:
        """Single navigation attempt with honest failure reporting."""
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
            return ToolResult.ok("browser", "loaded")
        except PWTimeout:
            # The page may still have loaded partially; verify before judging.
            try:
                title = (await self._page.title()).strip()
                cur = self._page.url
            except Exception:  # noqa: BLE001
                return ToolResult.fail(
                    "browser", f"Timed out loading {url}.", error_code="NAV_TIMEOUT"
                )
            if _is_unlikely_blank(cur) or title:
                return ToolResult.ok("browser", "loaded-partial")
            return ToolResult.fail(
                "browser", f"Timed out loading {url}.", error_code="NAV_TIMEOUT"
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult.fail(
                "browser", f"Could not load {url}: {e}", error_code="NAV_FAILED"
            )

    async def navigate(self, url: str) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready

            target = normalize_url(url)
            attempts = 2 if _is_unlikely_blank(target) else 1
            last_error: Optional[str] = None

            for attempt in range(attempts):
                if attempt > 0:
                    await asyncio.sleep(1.2)  # brief pause before the retry
                    logger.info("browser_navigate_retry", url=target, attempt=attempt + 1)
                result = await self._goto(target)
                if not result.success:
                    last_error = result.error or result.message
                    continue

                await asyncio.sleep(0.8)
                title = (await self._page.title()).strip()
                current_url = self._page.url
                body = await self._read_page_snippet()
                error_marker = await self._looks_like_error_page(title, body)

                if error_marker:
                    last_error = (
                        f"The page did not load properly ({error_marker}). "
                        "Check the address or your internet connection."
                    )
                    continue  # retry once - transient DNS/network hiccups are common

                verified = _is_unlikely_blank(current_url) and not error_marker
                return ToolResult.ok(
                    "browser",
                    message=f"Loaded {current_url} in {self.browser_name}.",
                    data={"url": current_url, "title": title, "browser": self.browser_name},
                    output=title,
                    verification_passed=bool(verified or title),
                    context_updates={
                        "current_url": current_url,
                        "current_page_title": title,
                        "current_browser": self.browser_name,
                    },
                )

            return ToolResult.fail(
                "browser", last_error or f"Could not load {url}.", error_code="NAV_FAILED"
            )

    async def search(self, query: str, site: str = "google") -> ToolResult:
        engine = (site or "google").strip().lower()
        template = _SEARCH_ENGINES.get(engine, _SEARCH_ENGINES["google"])
        if engine not in _SEARCH_ENGINES and engine not in ("the web", "web", "internet"):
            template = _SEARCH_ENGINES.get(engine, _SEARCH_ENGINES["google"])
        import urllib.parse
        url = template.format(q=urllib.parse.quote(query))
        result = await self.navigate(url)
        if result.success:
            result.data = result.data or {}
            result.data["query"] = query
            result.data["site"] = engine
            result.context_updates = result.context_updates or {}
            result.context_updates.update({"last_search_query": query, "current_page_type": f"{engine}_search"})
        return result

    async def click(
        self,
        selector: Optional[str] = None,
        index: int = 0,
        text: Optional[str] = None,
    ) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready
            try:
                if selector:
                    locator = self._page.locator(selector)
                    count = await locator.count()
                    if count == 0:
                        return ToolResult.fail(
                            "browser", f"No element matched '{selector}'.", error_code="ELEMENT_NOT_FOUND"
                        )
                    if index >= count:
                        return ToolResult.fail(
                            "browser",
                            f"Index {index} is out of range for '{selector}' ({count} found).",
                            error_code="ELEMENT_NOT_FOUND",
                        )
                    await locator.nth(index).scroll_into_view_if_needed(timeout=4000)
                    await locator.nth(index).click(timeout=6000)
                elif text:
                    clicked = await self._click_by_text(text)
                    if not clicked:
                        return ToolResult.fail(
                            "browser",
                            f"Could not find a clickable element containing '{text}'.",
                            error_code="ELEMENT_NOT_FOUND",
                        )
                else:
                    # Default: click the first link/button on the page.
                    locator = self._page.locator("a, button")
                    if await locator.count() == 0:
                        return ToolResult.fail(
                            "browser", "No clickable elements found on this page.",
                            error_code="ELEMENT_NOT_FOUND",
                        )
                    await locator.nth(0).click(timeout=6000)
            except PWTimeout:
                return ToolResult.fail(
                    "browser", "Timed out while clicking the element.", error_code="CLICK_TIMEOUT"
                )
            except Exception as e:  # noqa: BLE001
                return ToolResult.fail("browser", f"Click failed: {e}", error_code="CLICK_FAILED")

            await asyncio.sleep(1.0)
            title = (await self._page.title()).strip()
            current_url = self._page.url
            return ToolResult.ok(
                "browser",
                message=f"Clicked element{' ' + selector if selector else ''} (index {index}).",
                data={"url": current_url, "title": title, "index": index},
                output=title,
                context_updates={
                    "current_url": current_url, "current_page_title": title,
                    "selected_result_index": index,
                },
            )

    async def _click_by_text(self, text: str) -> bool:
        """Try progressively specific text matches; returns True on success."""
        candidates = [
            f"a:has-text('{text}')",
            f"button:has-text('{text}')",
            f"a:has-text('{text}') >> nth=0",
        ]
        for sel in candidates:
            try:
                loc = self._page.locator(sel)
                if await loc.count() > 0:
                    await loc.first.click(timeout=5000)
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def press_key(self, key: str) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready
            mapped = key.strip()
            if mapped.lower() in ("enter", "return"):
                mapped = "Enter"
            elif mapped.lower() == "f":
                mapped = "KeyF"
            elif mapped.lower() in ("f11",):
                mapped = "F11"
            elif mapped.lower() in ("esc", "escape"):
                mapped = "Escape"
            elif mapped.lower() in ("space",):
                mapped = "Space"
            elif mapped.lower() in ("tab",):
                mapped = "Tab"
            try:
                if mapped == "KeyF":
                    await self._page.keyboard.press("KeyF")
                else:
                    await self._page.keyboard.press(mapped)
            except Exception as e:  # noqa: BLE001
                return ToolResult.fail("browser", f"Key press failed: {e}", error_code="KEY_FAILED")
            return ToolResult.ok("browser", message=f"Pressed {key}.", data={"key": key})

    async def type_text(self, text: str) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready
            try:
                await self._page.keyboard.type(str(text), delay=30)
            except Exception as e:  # noqa: BLE001
                return ToolResult.fail("browser", f"Typing failed: {e}", error_code="TYPE_FAILED")
            return ToolResult.ok("browser", message=f"Typed {len(str(text))} characters.")

    async def fullscreen(self) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready
            try:
                await self._page.keyboard.press("F11")
            except Exception as e:  # noqa: BLE001
                return ToolResult.fail("browser", f"Fullscreen toggle failed: {e}", error_code="FULLSCREEN_FAILED")
            return ToolResult.ok("browser", message="Toggled fullscreen.", data={"fullscreen": True})

    async def snapshot(self, limit: int = 40) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready
            try:
                title = (await self._page.title()).strip()
                url = self._page.url
                texts = await self._page.locator("a, button").all_inner_texts()
            except Exception as e:  # noqa: BLE001
                return ToolResult.fail("browser", f"Snapshot failed: {e}", error_code="SNAPSHOT_FAILED")
            clickable = []
            seen = set()
            for t in texts:
                cleaned = " ".join(t.split())
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    clickable.append({"text": cleaned[:120]})
                if len(clickable) >= limit:
                    break
            return ToolResult.ok(
                "browser",
                message=f"Captured page: {title}",
                data={"title": title, "url": url, "clickable_elements": clickable},
                output=f"{title}\n" + "\n".join(c["text"] for c in clickable[:25]),
                context_updates={
                    "current_url": url, "current_page_title": title,
                    "visible_elements": clickable,
                },
            )


browser_manager = BrowserManager()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
class OpenUrlTool(TerminalTool):
    name = "open_url"
    description = (
        "Opens a URL in the PLUTO browser (or navigates the current tab). "
        "Use for 'open YouTube', 'open a website', etc."
    )
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL (https:// optional)"}},
            "required": ["url"],
        }

    async def execute(self, url: str, **kwargs) -> ToolResult:
        return await browser_manager.navigate(url)


class BrowserSearchTool(TerminalTool):
    name = "browser_search"
    description = (
        "Searches a site from the browser. Supported sites: youtube, google, "
        "duckduckgo, bing, wikipedia, reddit, github, amazon, maps."
    )
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text"},
                "site": {"type": "string", "description": "Site to search (default: google)", "default": "google"},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, site: str = "google", **kwargs) -> ToolResult:
        return await browser_manager.search(query, site)


class BrowserClickTool(TerminalTool):
    name = "browser_click"
    description = (
        "Clicks an element on the current page. Provide 'selector' (e.g. "
        "'a#video-title'), an optional zero-based 'index' (e.g. 1 = the second "
        "match), or 'text' to click a link/button whose text matches."
    )
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector (optional)"},
                "index": {"type": "integer", "description": "Zero-based index among matches", "default": 0},
                "text": {"type": "string", "description": "Match clickable text (optional)"},
            },
            "required": [],
        }

    async def execute(
        self, selector: Optional[str] = None, index: int = 0, text: Optional[str] = None, **kwargs
    ) -> ToolResult:
        return await browser_manager.click(selector, int(index or 0), text)


class BrowserKeyTool(TerminalTool):
    name = "browser_key"
    description = "Presses a keyboard key in the browser: Enter, Tab, Escape, f (fullscreen), Space, arrow keys..."
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Key to press"}},
            "required": ["key"],
        }

    async def execute(self, key: str, **kwargs) -> ToolResult:
        return await browser_manager.press_key(key)


class BrowserTypeTool(TerminalTool):
    name = "browser_type"
    description = "Types text into the focused element of the browser page (e.g. a search box)."
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to type"}},
            "required": ["text"],
        }

    async def execute(self, text: str, **kwargs) -> ToolResult:
        return await browser_manager.type_text(text)


class BrowserFullscreenTool(TerminalTool):
    name = "browser_fullscreen"
    description = "Toggles fullscreen in the browser."
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        return await browser_manager.fullscreen()


class BrowserSnapshotTool(TerminalTool):
    name = "browser_snapshot"
    description = "Reads the current page: title, URL, and the clickable elements visible on it."
    safety_level = SafetyLevel.SAFE
    category = "browser"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        return await browser_manager.snapshot()


BROWSER_TOOLS: List[TerminalTool] = [
    OpenUrlTool(),
    BrowserSearchTool(),
    BrowserClickTool(),
    BrowserKeyTool(),
    BrowserTypeTool(),
    BrowserFullscreenTool(),
    BrowserSnapshotTool(),
]
