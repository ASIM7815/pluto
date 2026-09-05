"""Tool Registry for PLUTO Agent"""
from typing import Dict, Any, Callable, List
from app.schemas.tools import ToolDefinition, ToolResult
from app.tools.filesystem import filesystem_tools
from app.tools.applications import application_tools
from app.tools.system import system_tools
from app.tools.terminal import terminal_tools
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Central registry for all PLUTO tools"""
    
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register all default tools"""
        
        # Filesystem tools
        self.register_tool(
            name="create_file",
            description="Create a new file with content",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path"]
            },
            permission_level="SAFE",
            category="filesystem",
            handler=filesystem_tools.create_file
        )
        
        self.register_tool(
            name="read_file",
            description="Read file content",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            },
            permission_level="SAFE",
            category="filesystem",
            handler=filesystem_tools.read_file
        )
        
        self.register_tool(
            name="list_directory",
            description="List directory contents",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            },
            permission_level="SAFE",
            category="filesystem",
            handler=filesystem_tools.list_directory
        )
        
        self.register_tool(
            name="create_directory",
            description="Create a new directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            },
            permission_level="SAFE",
            category="filesystem",
            handler=filesystem_tools.create_directory
        )
        
        self.register_tool(
            name="delete_file",
            description="Delete a file or directory (requires confirmation)",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File/directory path"}
                },
                "required": ["path"]
            },
            permission_level="CONFIRM_REQUIRED",
            category="filesystem",
            handler=filesystem_tools.delete_file
        )
        
        # Application tools
        self.register_tool(
            name="open_application",
            description="Launch an application",
            parameters={
                "type": "object",
                "properties": {
                    "application": {"type": "string", "description": "Application name"},
                    "workspace": {"type": "string", "description": "Optional workspace/file path"},
                    "arguments": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["application"]
            },
            permission_level="SAFE",
            category="application",
            handler=application_tools.open_application
        )
        
        self.register_tool(
            name="open_url",
            description="Open URL in default browser",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"}
                },
                "required": ["url"]
            },
            permission_level="SAFE",
            category="browser",
            handler=application_tools.open_url
        )
        
        # System tools
        self.register_tool(
            name="get_processes",
            description="Get list of running processes",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of processes"}
                }
            },
            permission_level="SAFE",
            category="system",
            handler=system_tools.get_running_processes
        )
        
        # Terminal
        self.register_tool(
            name="execute_command",
            description="Execute terminal command (use with caution)",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "working_directory": {"type": "string"},
                    "timeout": {"type": "integer", "default": 30}
                },
                "required": ["command"]
            },
            permission_level="CONFIRM_REQUIRED",
            category="terminal",
            handler=terminal_tools.execute_command
        )
    
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        permission_level: str,
        category: str,
        handler: Callable
    ):
        """Register a new tool"""
        self.tools[name] = {
            "definition": ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                permission_level=permission_level,
                category=category
            ),
            "handler": handler
        }
        logger.info("tool_registered", tool=name, permission=permission_level)
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for LLM (OpenAI function calling format)"""
        definitions = []
        for name, tool_data in self.tools.items():
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool_data["definition"].description,
                    "parameters": tool_data["definition"].parameters
                }
            })
        return definitions
    
    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a registered tool"""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                tool=tool_name,
                error={"code": "TOOL_NOT_FOUND", "message": f"Tool not found: {tool_name}"}
            )
        
        try:
            handler = self.tools[tool_name]["handler"]
            result = await handler(**kwargs)
            return result
        except Exception as e:
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            return ToolResult(
                success=False,
                tool=tool_name,
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )
    
    def get_permission_level(self, tool_name: str) -> str:
        """Get permission level for a tool"""
        if tool_name in self.tools:
            return self.tools[tool_name]["definition"].permission_level
        return "BLOCKED"


# Singleton instance
tool_registry = ToolRegistry()
