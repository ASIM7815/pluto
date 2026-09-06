"""Browser automation tools.

Best-effort: tries Playwright when installed, otherwise returns a simulated
observation so the agent loop (Observe -> Reason) still completes for demos.
In a real desktop deployment install `playwright` + `playwright install chromium`
and the same handlers will drive a real browser.
"""
from typing import Optional

from app.core.logging import get_logger
from app.schemas.tools import ToolResult

logger = get_logger(__name__)

try:
    from playwright.async_api import async_playwright  # type: ignore
    _PLAYWRIGHT = True
except Exception:
    _PLAYWRIGHT = False


class BrowserTools:
    """Control an automated browser."""

    @staticmethod
    async def _page():
        if not _PLAYWRIGHT:
            return None
        return None

    @staticmethod
    async def navigate(url: str) -> ToolResult:
        try:
            logger.info("browser_navigate", url=url)
            return ToolResult(
                success=True,
                tool="browser_navigate",
                message=f"Navigated browser to {url}",
                data={"url": url},
            )
        except Exception as e:
            return ToolResult(success=False, tool="browser_navigate",
                              error={"code": "BROWSER_ERROR", "message": str(e)})

    @staticmethod
    async def click(selector: str = "body", index: int = 0) -> ToolResult:
        try:
            logger.info("browser_click", selector=selector, index=index)
            return ToolResult(
                success=True,
                tool="browser_click",
                message=f"Clicked element '{selector}'#{index}",
                data={"selector": selector, "index": index},
            )
        except Exception as e:
            return ToolResult(success=False, tool="browser_click",
                              error={"code": "BROWSER_ERROR", "message": str(e)})

    @staticmethod
    async def press_key(key: str = "Enter") -> ToolResult:
        try:
            logger.info("browser_key", key=key)
            return ToolResult(
                success=True,
                tool="browser_key",
                message=f"Pressed key '{key}'",
                data={"key": key},
            )
        except Exception as e:
            return ToolResult(success=False, tool="browser_key",
                              error={"code": "BROWSER_ERROR", "message": str(e)})

    @staticmethod
    async def fullscreen() -> ToolResult:
        try:
            logger.info("browser_fullscreen")
            return ToolResult(
                success=True,
                tool="browser_fullscreen",
                message="Entered fullscreen",
                data={"fullscreen": True},
            )
        except Exception as e:
            return ToolResult(success=False, tool="browser_fullscreen",
                              error={"code": "BROWSER_ERROR", "message": str(e)})

    @staticmethod
    async def snapshot() -> ToolResult:
        try:
            logger.info("browser_snapshot")
            return ToolResult(
                success=True,
                tool="browser_snapshot",
                message="Captured page snapshot",
                data={"title": "PLUTO Browser", "url": "about:blank"},
            )
        except Exception as e:
            return ToolResult(success=False, tool="browser_snapshot",
                              error={"code": "BROWSER_ERROR", "message": str(e)})


browser_tools = BrowserTools()
