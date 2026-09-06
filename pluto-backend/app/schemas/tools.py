"""Tool and Context schemas for PLUTO Level 1"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal, Callable
from datetime import datetime


# Tool Safety Levels
ToolSafetyLevel = Literal["safe", "confirm", "dangerous"]

# Tool Categories
ToolCategory = Literal["application", "file", "system", "browser"]


# Legacy schemas (for backward compatibility with old tool_registry.py)
class ToolDefinition(BaseModel):
    """Legacy tool definition schema"""
    name: str
    description: str
    parameters: Dict[str, Any]
    
    class Config:
        arbitrary_types_allowed = True


class ToolResult(BaseModel):
    """Legacy tool result schema"""
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    tool: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class ToolSchema(BaseModel):
    """OpenAI function schema for a tool"""
    name: str
    description: str
    parameters: Dict[str, Any]
    category: Optional[ToolCategory] = None
    safety_level: Optional[ToolSafetyLevel] = "safe"


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool"""
    tool_name: str
    parameters: Dict[str, Any]
    skip_safety_check: bool = False


class ToolExecutionResult(BaseModel):
    """Result of tool execution"""
    success: bool
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    verification_passed: bool = True
    context_updates: Optional[Dict[str, Any]] = None


class ToolInfo(BaseModel):
    """Information about a registered tool"""
    name: str
    description: str
    category: ToolCategory
    safety_level: ToolSafetyLevel
    parameters: Dict[str, Any]


class ToolRegistryInfo(BaseModel):
    """Information about the tool registry"""
    total_tools: int
    categories: Dict[str, int]
    tools: List[ToolInfo]


# Context Tracking Schemas

class ActionRecord(BaseModel):
    """Record of an action taken by PLUTO"""
    tool: str
    parameters: Dict[str, Any]
    result: str
    success: bool
    timestamp: datetime


class BrowserContext(BaseModel):
    """Browser-specific context"""
    url: Optional[str] = None
    title: Optional[str] = None
    page_type: Optional[Literal["search", "video", "article", "app", "other"]] = None


class SearchContext(BaseModel):
    """Search-related context"""
    query: Optional[str] = None
    results: List[Dict[str, Any]] = []


class SessionContext(BaseModel):
    """Complete session context"""
    session_id: str
    current_app: Optional[str] = None
    active_window: Optional[str] = None
    current_directory: Optional[str] = None
    browser: Optional[BrowserContext] = None
    search: Optional[SearchContext] = None
    recent_actions: List[ActionRecord] = []
    recent_files: List[str] = []
    volume_level: Optional[int] = None
    volume_muted: Optional[bool] = None


class ContextSummary(BaseModel):
    """Human-readable context summary for LLM"""
    summary: str
    current_app: Optional[str] = None
    browser_url: Optional[str] = None
    recent_actions_count: int = 0
    has_search_results: bool = False


class ContextUpdateRequest(BaseModel):
    """Request to update session context"""
    updates: Dict[str, Any]


# Intent Detection Schemas

class UserIntent(BaseModel):
    """Detected user intent"""
    intent_type: Literal[
        "open_app",
        "close_app",
        "switch_app",
        "open_file",
        "find_file",
        "create_folder",
        "screenshot",
        "volume_control",
        "clipboard",
        "browser_action",
        "search",
        "silence",
        "other"
    ]
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any]
    recommended_tools: List[str] = []


class IntentAnalysisRequest(BaseModel):
    """Request to analyze user intent"""
    command: str
    context: Optional[Dict[str, Any]] = None


class IntentAnalysisResponse(BaseModel):
    """Response from intent analysis"""
    intent: UserIntent
    context_aware: bool
    reasoning: Optional[str] = None


# Tool Recommendation Schemas

class ToolRecommendation(BaseModel):
    """Recommended tool for a given intent"""
    tool_name: str
    confidence: float
    reasoning: str
    suggested_parameters: Optional[Dict[str, Any]] = None


class ToolRecommendationRequest(BaseModel):
    """Request for tool recommendations"""
    intent: str
    context: Optional[Dict[str, Any]] = None


class ToolRecommendationResponse(BaseModel):
    """Response with tool recommendations"""
    recommendations: List[ToolRecommendation]
    context_used: bool


# Verification Schemas

class VerificationRequest(BaseModel):
    """Request to verify tool execution"""
    tool_name: str
    result: ToolExecutionResult
    parameters: Dict[str, Any]


class VerificationResponse(BaseModel):
    """Result of verification"""
    verified: bool
    details: Optional[str] = None
    issues: List[str] = []


# System Status Schemas

class SystemStatus(BaseModel):
    """System status for PLUTO"""
    state: Literal[
        "idle",
        "listening",
        "understanding",
        "thinking",
        "planning",
        "executing",
        "verifying",
        "speaking"
    ]
    tools_available: int
    context_active: bool
    continuous_listening: bool
    last_action: Optional[str] = None
    uptime_seconds: Optional[float] = None


class SystemCapabilities(BaseModel):
    """System capabilities"""
    level: int  # 1 = desktop control, 2 = browser automation, etc.
    features: List[str]
    tools_by_category: Dict[str, List[str]]
    continuous_listening: bool
    context_awareness: bool
    verification_enabled: bool
