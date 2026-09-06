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
from typing import Any, Dict, List, Optional

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


def _is_unlikely_blank(url: str) -> bool:
    return bool(url and url not in ("about:blank", ""))


class BrowserManager:
    """Lazy Playwright browser with a lock-serialised active page."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pw = None
        self._browser = None
        self._page = None

    @property
    def available(self) -> bool:
        return _PLAYWRIGHT_AVAILABLE

    async def _ensure(self) -> ToolResult:
        if not _PLAYWRIGHT_AVAILABLE:
            return ToolResult.fail("browser", _MISSING_HINT, error_code="MISSING_DEPENDENCY")
        if self._browser and self._page:
            return ToolResult.ok("browser", "ready")
        try:
            self._pw = await async_playwright().start()
            headless = settings.pluto_browser_headless
            if headless == "auto":
                headless = not has_display()
            launch_kwargs: Dict[str, Any] = {"headless": headless}
            if os.environ.get("PLUTO_BROWSER_EXECUTABLE"):
                launch_kwargs["executable_path"] = os.environ["PLUTO_BROWSER_EXECUTABLE"]
            self._browser = await self._pw.chromium.launch(**launch_kwargs)
            self._page = await self._browser.new_page()
            logger.info("browser_started", headless=bool(headless))
            return ToolResult.ok("browser", "started")
        except Exception as e:  # noqa: BLE001
            logger.error("browser_start_error", error=str(e))
            # NOTE: _ensure is always called while the caller holds the lock,
            # so close() must NOT try to re-acquire it (that would deadlock).
            await self._close_unlocked()
            return ToolResult.fail(
                "browser",
                f"Could not start the browser: {e}. {_MISSING_HINT}",
                error_code="BROWSER_START_FAILED",
            )

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()

    async def _close_unlocked(self) -> None:
        """Release browser resources. Caller must already hold ``_lock``."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._browser = None
        self._page = None
        self._pw = None

    # ------------------------------------------------------------------
    async def navigate(self, url: str) -> ToolResult:
        async with self._lock:
            ready = await self._ensure()
            if not ready.success:
                return ready
            if not re.match(r"^https?://", url):
                url = "https://" + url
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except PWTimeout:
                # The page may still have loaded partially; report truthfully.
                title = await self._page.title()
                cur = self._page.url
                if not _is_unlikely_blank(cur) and not title:
                    return ToolResult.fail(
                        "browser", f"Timed out loading {url}.", error_code="NAV_TIMEOUT"
                    )
            except Exception as e:  # noqa: BLE001
                return ToolResult.fail(
                    "browser", f"Could not load {url}: {e}", error_code="NAV_FAILED"
                )
            await asyncio.sleep(0.8)
            title = (await self._page.title()).strip()
            current_url = self._page.url
            return ToolResult.ok(
                "browser",
                message=f"Loaded {current_url}.",
                data={"url": current_url, "title": title},
                output=title,
                verification_passed=_is_unlikely_blank(current_url) or bool(title),
                context_updates={
                    "current_url": current_url,
                    "current_page_title": title,
                    "current_browser": "chromium",
                },
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
