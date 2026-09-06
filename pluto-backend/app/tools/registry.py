"""Tool Registry V2 - Central registry for all PLUTO tools with GPT function calling support"""
from typing import Dict, List, Any, Optional
from app.tools.terminal_base import TerminalTool, ToolResult, SafetyLevel
from app.tools.application_tools import APPLICATION_TOOLS
from app.tools.file_tools import FILE_TOOLS
from app.tools.system_tools import SYSTEM_TOOLS
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Central registry for all PLUTO tools
    
    Provides:
    - Tool registration and lookup
    - OpenAI function schema generation
    - Tool execution with safety checks
    - Context-aware tool recommendations
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.tools: Dict[str, TerminalTool] = {}
        self.tools_by_category: Dict[str, List[str]] = {
            "application": [],
            "file": [],
            "system": [],
            "browser": [],
        }
        
        # Register all tools
        self._register_tools()
        self._initialized = True
        
        logger.info(
            "tool_registry_initialized",
            total_tools=len(self.tools),
            categories=list(self.tools_by_category.keys())
        )
    
    def _register_tools(self):
        """Register all available tools"""
        # Application tools
        for tool in APPLICATION_TOOLS:
            self._register_tool(tool, "application")
        
        # File tools
        for tool in FILE_TOOLS:
            self._register_tool(tool, "file")
        
        # System tools
        for tool in SYSTEM_TOOLS:
            self._register_tool(tool, "system")
        
        # Browser tools will be added later
        # TODO: Add browser automation tools (Playwright)
    
    def _register_tool(self, tool: TerminalTool, category: str):
        """Register a single tool"""
        self.tools[tool.name] = tool
        self.tools_by_category[category].append(tool.name)
        logger.debug(
            "tool_registered",
            name=tool.name,
            category=category,
            safety=tool.safety_level
        )
    
    def get_tool(self, name: str) -> Optional[TerminalTool]:
        """
        Get a tool by name
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None
        """
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[TerminalTool]:
        """
        Get all tools in a category
        
        Args:
            category: Category name
            
        Returns:
            List of tools
        """
        tool_names = self.tools_by_category.get(category, [])
        return [self.tools[name] for name in tool_names]
    
    def get_all_tools(self) -> List[TerminalTool]:
        """
        Get all registered tools
        
        Returns:
            List of all tools
        """
        return list(self.tools.values())
    
    def get_tool_schemas(self, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get OpenAI function schemas for tools
        
        Args:
            categories: Filter by categories (optional)
            
        Returns:
            List of OpenAI function schemas
        """
        if categories:
            tools = []
            for category in categories:
                tools.extend(self.get_tools_by_category(category))
        else:
            tools = self.get_all_tools()
        
        schemas = []
        for tool in tools:
            try:
                schema = tool.get_schema()
                schemas.append(schema)
            except Exception as e:
                logger.error(
                    "tool_schema_error",
                    tool=tool.name,
                    error=str(e)
                )
        
        return schemas
    
    def get_safe_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get schemas for SAFE tools only (auto-executable)
        
        Returns:
            List of schemas for safe tools
        """
        safe_tools = [
            tool for tool in self.get_all_tools()
            if tool.safety_level == SafetyLevel.SAFE
        ]
        
        return [tool.get_schema() for tool in safe_tools]
    
    def get_context_aware_schemas(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get tool schemas relevant to current context
        
        Args:
            context: Current context (from ContextManager)
            
        Returns:
            List of relevant tool schemas
        """
        # Start with all tools
        relevant_tools = self.get_all_tools()
        
        # Filter based on context
        current_app = context.get("current_app")
        browser_url = context.get("browser_url")
        
        # If browser is open, include browser tools
        if browser_url or (current_app and "firefox" in current_app.lower()):
            # Include browser category when implemented
            pass
        
        # Always include application, file, and system tools
        # These are the core Level 1 capabilities
        
        return [tool.get_schema() for tool in relevant_tools]
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        skip_safety_check: bool = False
    ) -> ToolResult:
        """
        Execute a tool with safety checks
        
        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters
            skip_safety_check: Skip safety confirmation (for testing)
            
        Returns:
            ToolResult
        """
        # Get tool
        tool = self.get_tool(tool_name)
        if not tool:
            logger.error("tool_not_found", name=tool_name)
            return ToolResult(
                success=False,
                message=f"Tool not found: {tool_name}",
                error="Unknown tool"
            )
        
        # Safety check
        if not skip_safety_check and tool.safety_level == SafetyLevel.CONFIRM_REQUIRED:
            logger.warning(
                "tool_requires_confirmation",
                tool=tool_name,
                safety=tool.safety_level
            )
            # In production, this would trigger user confirmation
            # For now, we log and proceed
        
        if tool.safety_level == SafetyLevel.DANGEROUS:
            logger.error(
                "tool_blocked",
                tool=tool_name,
                safety=tool.safety_level
            )
            return ToolResult(
                success=False,
                message=f"Tool {tool_name} requires explicit permission",
                error="Dangerous operation blocked"
            )
        
        # Execute tool
        try:
            logger.info(
                "tool_execution_start",
                tool=tool_name,
                params=list(parameters.keys())
            )
            
            result = await tool.execute(**parameters)
            
            logger.info(
                "tool_execution_complete",
                tool=tool_name,
                success=result.success,
                verification=result.verification_passed
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "tool_execution_error",
                tool=tool_name,
                error=str(e)
            )
            return ToolResult(
                success=False,
                message=f"Error executing {tool_name}: {str(e)}",
                error=str(e)
            )
    
    async def verify_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
        parameters: Dict[str, Any]
    ) -> bool:
        """
        Verify a tool execution result
        
        Args:
            tool_name: Tool name
            result: Execution result
            parameters: Original parameters
            
        Returns:
            True if verification passed
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False
        
        try:
            verified = await tool.verify(result, **parameters)
            logger.info(
                "tool_verification",
                tool=tool_name,
                verified=verified
            )
            return verified
        except Exception as e:
            logger.error(
                "tool_verification_error",
                tool=tool_name,
                error=str(e)
            )
            return False
    
    def get_tool_info(self) -> Dict[str, Any]:
        """
        Get registry information
        
        Returns:
            Registry stats and tool list
        """
        return {
            "total_tools": len(self.tools),
            "categories": {
                category: len(tools)
                for category, tools in self.tools_by_category.items()
            },
            "tools": {
                name: {
                    "description": tool.description,
                    "safety_level": tool.safety_level,
                    "category": self._get_tool_category(name)
                }
                for name, tool in self.tools.items()
            }
        }
    
    def _get_tool_category(self, tool_name: str) -> Optional[str]:
        """Get category for a tool"""
        for category, tools in self.tools_by_category.items():
            if tool_name in tools:
                return category
        return None
    
    def get_recommended_tools(self, intent: str, context: Dict[str, Any]) -> List[str]:
        """
        Recommend tools based on user intent and context
        
        Args:
            intent: User's intent/command
            context: Current context
            
        Returns:
            List of recommended tool names
        """
        intent_lower = intent.lower()
        recommended = []
        
        # Intent-based recommendations
        if any(word in intent_lower for word in ["open", "launch", "start"]):
            if any(word in intent_lower for word in ["file", "folder", "directory"]):
                recommended.extend(["open_file", "open_folder"])
            else:
                recommended.append("open_application")
        
        if any(word in intent_lower for word in ["close", "quit", "exit"]):
            recommended.append("close_application")
        
        if any(word in intent_lower for word in ["switch", "focus", "go to"]):
            recommended.append("switch_to_application")
        
        if any(word in intent_lower for word in ["find", "search", "locate"]):
            if any(word in intent_lower for word in ["file", "document"]):
                recommended.append("find_files")
        
        if any(word in intent_lower for word in ["screenshot", "capture", "snap"]):
            recommended.append("take_screenshot")
        
        if any(word in intent_lower for word in ["volume", "sound", "audio"]):
            recommended.extend(["set_volume", "get_volume"])
        
        if any(word in intent_lower for word in ["copy", "clipboard"]):
            recommended.extend(["copy_to_clipboard", "get_clipboard"])
        
        if any(word in intent_lower for word in ["create", "make", "new"]):
            if "folder" in intent_lower:
                recommended.append("create_folder")
        
        if any(word in intent_lower for word in ["move", "rename"]):
            recommended.append("move_file")
        
        return recommended


# Global registry instance
_registry = None


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry instance
    
    Returns:
        ToolRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: TerminalTool, category: str):
    """
    Register a tool with the global registry
    
    Args:
        tool: Tool instance
        category: Tool category
    """
    registry = get_registry()
    registry._register_tool(tool, category)
