"""Chat, command and loop event schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any


# PLUTO States (matches frontend + loop states). The StateMachine enum mirrors
# this list, so every value here must exist in agent/state_machine.py.
PlutoState = Literal[
    "idle",
    "listening",
    "understanding",
    "thinking",
    "planning",
    "executing",
    "verifying",
    "observing",
    "reasoning",
    "speaking",
    "success",
    "error",
]

# Event types the backend can emit over the WebSocket.
EventType = Literal[
    "agent_state",
    "execution_step",
    "activity",
    "action_preview",
    "speak",
    "error",
    "session",
    "silence",
    "interrupted",
]

TtsEngine = Literal["elevenlabs", "browser", "local_tts"]


class CommandRequest(BaseModel):
    """User command/query request (REST)."""
    command: str = Field(..., min_length=1, max_length=4000)
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ExecutionStep(BaseModel):
    """Execution step (matches frontend)."""
    id: str
    label: str
    status: Literal["completed", "current", "pending", "error"]
    detail: Optional[str] = None


class Activity(BaseModel):
    """Activity log item (matches frontend)."""
    id: str
    title: str
    description: str
    timestamp: str
    status: Literal["running", "success", "info", "error"]
    category: Optional[Literal[
        "app", "file", "message", "system", "automation", "browser"
    ]] = None


class ActionPreview(BaseModel):
    """Action preview for confirmation (matches frontend)."""
    type: Literal["email", "message", "file_delete", "command", "automation", "browser"]
    title: str
    recipient: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    fileCount: Optional[int] = None
    path: Optional[str] = None
    meta: Optional[Dict[str, str]] = None
    requiresConfirmation: bool


class SpeakEvent(BaseModel):
    """Spoken response event sent to the frontend."""
    type: Literal["speak"]
    text: str
    # base64-encoded audio bytes, or null => frontend uses browser speechSynthesis
    audio: Optional[str] = None
    tts: TtsEngine = "browser"


class AgentStateEvent(BaseModel):
    """WebSocket event for agent state changes / session metadata."""
    type: EventType
    state: Optional[PlutoState] = None
    task: Optional[str] = None
    step: Optional[ExecutionStep] = None
    activity: Optional[Activity] = None
    preview: Optional[ActionPreview] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    # session info
    session_id: Optional[str] = None
    # speak payload
    text: Optional[str] = None
    audio: Optional[str] = None
    tts: Optional[TtsEngine] = None


class CommandResponse(BaseModel):
    """Response to command execution (REST)."""
    success: bool
    message: str
    state: PlutoState
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ConfirmRequest(BaseModel):
    """Frontend confirmation/rejection of a pending action."""
    session_id: Optional[str] = None
    action: str
    approved: bool = True
