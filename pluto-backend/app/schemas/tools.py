"""Tool-introspection and context REST schemas.

The internal tool execution result is the dataclass in
app/tools/terminal_base.py; these models describe the HTTP request/response
bodies only.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool directly (debugging / automation)."""
    tool_name: str
    parameters: Dict[str, Any] = {}
    skip_safety_check: bool = False
    session_id: Optional[str] = None


class ContextUpdateRequest(BaseModel):
    """Request to update a session's context."""
    updates: Dict[str, Any]
    session_id: Optional[str] = None


class IntentAnalysisRequest(BaseModel):
    """Request to analyze user intent."""
    command: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ToolRecommendation(BaseModel):
    tool_name: str
    confidence: float
    reasoning: str
    suggested_parameters: Optional[Dict[str, Any]] = None


class ToolRecommendationRequest(BaseModel):
    intent: str
    context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class ToolRecommendationResponse(BaseModel):
    recommendations: List[ToolRecommendation]
    context_used: bool


class VerificationRequest(BaseModel):
    tool_name: str
    result: Dict[str, Any]
    parameters: Dict[str, Any] = {}
    session_id: Optional[str] = None


class VerificationResponse(BaseModel):
    verified: bool
    details: Optional[str] = None
    issues: List[str] = []


class SystemStatus(BaseModel):
    state: str
    tools_available: int
    context_active: bool
    continuous_listening: bool
    last_action: Optional[str] = None
    uptime_seconds: Optional[float] = None
    session_id: Optional[str] = None


class SystemCapabilities(BaseModel):
    level: int
    features: List[str]
    tools_by_category: Dict[str, int]
    continuous_listening: bool
    context_awareness: bool
    verification_enabled: bool
