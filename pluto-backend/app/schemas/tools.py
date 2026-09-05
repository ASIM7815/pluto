"""Tool execution schemas"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal


class ToolRequest(BaseModel):
    """Tool execution request"""
    tool: str
    arguments: Dict[str, Any]
    require_confirmation: bool = False


class ToolResult(BaseModel):
    """Tool execution result"""
    success: bool
    tool: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
    message: Optional[str] = None


class ToolDefinition(BaseModel):
    """Tool definition for registry"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    permission_level: Literal["SAFE", "CONFIRM_REQUIRED", "BLOCKED"]
    category: Literal["filesystem", "application", "system", "browser", "terminal"]


class FileOperation(BaseModel):
    """Filesystem operation request"""
    operation: Literal["create", "read", "write", "delete", "list", "move", "copy"]
    path: str
    content: Optional[str] = None
    destination: Optional[str] = None


class ApplicationLaunch(BaseModel):
    """Application launch request"""
    application: str
    arguments: Optional[list[str]] = None
    workspace: Optional[str] = None


class TerminalCommand(BaseModel):
    """Terminal command execution request"""
    command: str
    working_directory: Optional[str] = None
    timeout: int = 30
