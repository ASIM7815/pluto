"""PLUTO Unified Tool Registry.

The single catalogue of every tool PLUTO can run. The registry provides:
- lookup & category organisation,
- OpenAI function-calling schemas for the LLM,
- safety-gated execution returning the canonical ToolResult,
- optional post-execution verification,
- intent-based recommendations.

There is intentionally only ONE registry in the codebase - the legacy V1
registry and its duplicated modules were removed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.tools.terminal_base import TerminalTool, ToolResult, SafetyLevel
from app.tools.application_tools import APPLICATION_TOOLS
from app.tools.file_tools import FILE_TOOLS
from app.tools.system_tools import SYSTEM_TOOLS
from app.tools.browser import BROWSER_TOOLS
from app.tools.messaging import MESSAGING_TOOLS
from app.tools.terminal import TERMINAL_TOOLS

logger = get_logger(__name__)

_CATEGORIES = ("application", "file", "system", "browser", "message", "terminal")


class ToolRegistry:
    """Central registry for all PLUTO tools."""

    _instance: Optional["ToolRegistry"] = None

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.tools: Dict[str, TerminalTool] = {}
        self.tools_by_category: Dict[str, List[str]] = {c: [] for c in _CATEGORIES}
        self._register_tools()
        self._initialized = True
        logger.info(
            "tool_registry_initialized",
            total_tools=len(self.tools),
            categories={c: len(v) for c, v in self.tools_by_category.items()},
        )

    def _register_tools(self) -> None:
        batches = [
            (APPLICATION_TOOLS, "application"),
            (FILE_TOOLS, "file"),
            (SYSTEM_TOOLS, "system"),
            (BROWSER_TOOLS, "browser"),
            (MESSAGING_TOOLS, "message"),
            (TERMINAL_TOOLS, "terminal"),
        ]
        for tools, category in batches:
            for tool in tools:
                self._register_tool(tool, category)

    def _register_tool(self, tool: TerminalTool, category: str) -> None:
        if not tool.name or tool.name in self.tools:
            logger.warning("duplicate_tool_skipped", name=tool.name)
            return
        self.tools[tool.name] = tool
        self.tools_by_category.setdefault(category, []).append(tool.name)
        logger.debug("tool_registered", name=tool.name, category=category, safety=tool.safety_level)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get_tool(self, name: str) -> Optional[TerminalTool]:
        return self.tools.get(name)

    def get_all_tools(self) -> List[TerminalTool]:
        return list(self.tools.values())

    def get_tools_by_category(self, category: str) -> List[TerminalTool]:
        return [self.tools[n] for n in self.tools_by_category.get(category, []) if n in self.tools]

    def _get_tool_category(self, tool_name: str) -> Optional[str]:
        for category, names in self.tools_by_category.items():
            if tool_name in names:
                return category
        return None

    # ------------------------------------------------------------------
    # LLM schemas
    # ------------------------------------------------------------------
    def get_tool_schemas(self, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """OpenAI function-calling tool objects (with type: function)."""
        tools = self.get_all_tools()
        if categories:
            tools = []
            for category in categories:
                tools.extend(self.get_tools_by_category(category))
        schemas: List[Dict[str, Any]] = []
        for tool in tools:
            try:
                schemas.append(tool.get_schema())
            except Exception as e:  # noqa: BLE001
                logger.error("tool_schema_error", tool=tool.name, error=str(e))
        return schemas

    def get_safe_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            tool.get_schema()
            for tool in self.get_all_tools()
            if tool.safety_level == SafetyLevel.SAFE
        ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        skip_safety_check: bool = False,
    ) -> ToolResult:
        """Execute a tool by name.

        ``skip_safety_check`` is used by the orchestrator AFTER it has applied
        its own confirmation gate; it must never be used to bypass DANGEROUS
        tools - those are always refused here.
        """
        tool = self.get_tool(tool_name)
        if tool is None:
            logger.error("tool_not_found", name=tool_name)
            return ToolResult.fail(tool_name, f"Tool not found: {tool_name}", error_code="TOOL_NOT_FOUND")

        if tool.safety_level == SafetyLevel.DANGEROUS:
            return ToolResult.fail(
                tool_name,
                "That operation is blocked by PLUTO's security policy.",
                error_code="BLOCKED",
            )
        if tool.safety_level == SafetyLevel.CONFIRM_REQUIRED and not skip_safety_check:
            return ToolResult.fail(
                tool_name,
                "That action requires confirmation before it can run.",
                error_code="CONFIRM_REQUIRED",
            )

        try:
            logger.info(
                "tool_execution_start", tool=tool_name, params=list((parameters or {}).keys())
            )
            result = await tool.execute(**(parameters or {}))
        except Exception as e:  # noqa: BLE001
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            return ToolResult.fail(
                tool_name, f"Error executing {tool_name}: {e}", error_code="EXECUTION_ERROR"
            )

        # Ensure the canonical ToolResult carries its tool name.
        if result.tool is None:
            result.tool = tool_name
        logger.info(
            "tool_execution_complete",
            tool=tool_name, success=result.success,
            verification=result.verification_passed,
        )
        return result

    async def verify_tool_result(
        self, tool_name: str, result: ToolResult, parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        tool = self.get_tool(tool_name)
        if tool is None:
            return False
        if result.verification_passed is not None:
            return bool(result.verification_passed)
        try:
            verified = await tool.verify(result, **(parameters or {}))
            logger.info("tool_verification", tool=tool_name, verified=verified)
            return bool(verified)
        except Exception as e:  # noqa: BLE001
            logger.error("tool_verification_error", tool=tool_name, error=str(e))
            return False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def get_tool_info(self) -> Dict[str, Any]:
        return {
            "total_tools": len(self.tools),
            "categories": {c: len(n) for c, n in self.tools_by_category.items()},
            "tools": {
                name: {
                    "description": tool.description,
                    "safety_level": tool.safety_level,
                    "category": self._get_tool_category(name),
                }
                for name, tool in self.tools.items()
            },
        }

    def list_tools_verbose(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": tool.description,
                "safety_level": tool.safety_level,
                "category": self._get_tool_category(name),
                "parameters": tool.get_parameters_schema(),
            }
            for name, tool in self.tools.items()
        ]

    def get_recommended_tools(self, intent: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Simple keyword-based recommendations (used by /intent/analyze)."""
        text = (intent or "").lower()
        words = f" {text} "
        recommended: List[str] = []

        has_web = any(k in text for k in ("youtube", "website", "web", "url", "site", "search", "google", "video"))
        has_chat = any(k in text for k in ("whatsapp", "telegram", "message", "signal"))

        # Context: continuing the current app/browser
        context = context or {}
        current_url = context.get("current_url") or ""
        current_app = context.get("current_app") or ""

        if has_web:
            if "search" in text or "google" in text or "youtube" in text:
                recommended.append("browser_search")
            else:
                recommended.append("open_url")
        elif "second video" in text or "next video" in text or "click" in text or "play the" in text:
            recommended.append("browser_click")
        elif has_chat:
            recommended.append("send_message")

        if any(k in words for k in (" open ", " launch ", " start ", "open_application")):
            recommended.append("open_application")
        if any(k in words for k in (" close ", " quit ", "exit")):
            recommended.append("close_application")
        if any(k in words for k in ("find ", "search for", " locate ")) and any(
            k in text for k in ("file", "document", "folder")
        ):
            recommended.append("find_files")
        if "folder" in text and any(k in text for k in ("create", "make", "new")):
            recommended.append("create_folder")
        if any(k in text for k in ("create file", "make a file", "write a file")):
            recommended.append("create_file")
        if any(k in text for k in ("move ", "rename ")) and "file" in text:
            recommended.append("move_file")
        if any(k in text for k in ("copy ", "duplicate")) and "file" in text:
            recommended.append("copy_file")
        if any(k in text for k in ("delete ", "remove ")) and any(k in text for k in ("file", "folder", "cache")):
            recommended.append("delete_file")
        if any(k in text for k in ("screenshot", "capture screen", "snapshot screen")):
            recommended.append("take_screenshot")
        if any(k in text for k in ("volume", "sound", "mute", "unmute")):
            recommended.append("set_volume")
        if "clipboard" in text and any(k in text for k in ("copy", "put")):
            recommended.append("copy_to_clipboard")
        if "clipboard" in text and any(k in text for k in ("get", "read", "what")):
            recommended.append("get_clipboard")
        if any(k in text for k in ("process", "task manager", "top processes", "system stats", "system status", "cpu", "ram", "memory")):
            recommended.append("get_processes")
        if any(k in text for k in ("terminal", "command ", "run ")) and "command" in text:
            recommended.append("execute_command")
        if any(k in text for k in ("open file", "open a file")):
            recommended.append("open_file")

        # De-duplicate while preserving order.
        seen = set()
        return [r for r in recommended if not (r in seen or seen.add(r))]


_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Return the global (singleton) tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: TerminalTool, category: str) -> None:
    """Register a tool with the global registry (used by tests/extensions)."""
    registry = get_registry()
    registry._register_tool(tool, category)
