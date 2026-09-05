"""Chat and command schemas"""
from pydantic import BaseModel
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime


# PLUTO States (matching frontend)
PlutoState = Literal[
    "idle",
    "listening",
    "understanding",
    "thinking",
    "planning",
    "executing",
    "success",
    "error"
]


class CommandRequest(BaseModel):
    """User command/query request"""
    command: str
    context: Optional[Dict[str, Any]] = None


class ExecutionStep(BaseModel):
    """Execution step (matches frontend)"""
    id: str
    label: str
    status: Literal["completed", "current", "pending", "error"]
    detail: Optional[str] = None


class Activity(BaseModel):
    """Activity log item (matches frontend)"""
    id: str
    title: str
    description: str
    timestamp: str
    status: Literal["running", "success", "info", "error"]
    category: Optional[Literal["app", "file", "message", "system", "automation"]] = None


class ActionPreview(BaseModel):
    """Action preview for confirmation (matches frontend)"""
    type: Literal["email", "message", "file_delete", "command", "automation"]
    title: str
    recipient: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    fileCount: Optional[int] = None
    path: Optional[str] = None
    meta: Optional[Dict[str, str]] = None
    requiresConfirmation: bool


class AgentStateEvent(BaseModel):
    """WebSocket event for agent state changes"""
    type: Literal["agent_state", "execution_step", "activity", "action_preview", "error"]
    state: Optional[PlutoState] = None
    task: Optional[str] = None
    step: Optional[ExecutionStep] = None
    activity: Optional[Activity] = None
    preview: Optional[ActionPreview] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class CommandResponse(BaseModel):
    """Response to command execution"""
    success: bool
    message: str
    state: PlutoState
    data: Optional[Dict[str, Any]] = None
