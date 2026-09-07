"""Tool introspection & context routes (unified, session-scoped).

Everything here operates on the SAME context manager and tool registry that
the orchestrator uses - there are no private duplicate instances.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.agent.context_manager import context_manager
from app.agent.session_manager import session_manager
from app.schemas.tools import (
    ToolExecutionRequest,
    ContextUpdateRequest,
    IntentAnalysisRequest,
    ToolRecommendationRequest,
    ToolRecommendationResponse,
    ToolRecommendation,
    VerificationRequest,
    VerificationResponse,
    SystemStatus,
    SystemCapabilities,
)
from app.tools.registry import get_registry
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])

tool_registry = get_registry()
START_TIME = time.time()


def _resolve_session_id(session_id: Optional[str]) -> Optional[str]:
    """Use the provided session id, else the most recent active session."""
    if session_id:
        return session_id
    active = session_manager.active_sessions()
    if not active:
        return None
    # Most recently touched session.
    sessions = [s for s in session_manager._sessions.values() if s.id in active]
    if not sessions:
        return None
    return max(sessions, key=lambda s: s.last_activity).id


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------
@router.get("")
async def list_tools() -> dict:
    tools = tool_registry.list_tools_verbose()
    return {"tools": tools, "count": len(tools)}


@router.get("/list")
async def list_tools_v2(category: Optional[str] = None) -> dict:
    tools = tool_registry.get_tools_by_category(category) if category else tool_registry.get_all_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "safety_level": t.safety_level,
                "category": tool_registry._get_tool_category(t.name),
            }
            for t in tools
        ],
        "count": len(tools),
    }


@router.get("/permissions")
async def tool_permissions() -> dict:
    return {name: tool.safety_level for name, tool in tool_registry.tools.items()}


@router.get("/registry")
async def get_tool_registry() -> dict:
    return tool_registry.get_tool_info()


# Compatibility aliases for the earlier "/v2/..." surface.
@router.get("/v2/registry")
async def get_tool_registry_v2() -> dict:
    return tool_registry.get_tool_info()


@router.get("/v2/list")
async def list_tools_v2_alias(category: Optional[str] = None) -> dict:
    return await list_tools_v2(category)


@router.get("/v2/{tool_name}")
async def get_tool_details(tool_name: str) -> dict:
    tool = tool_registry.get_tool(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return {
        "name": tool.name,
        "description": tool.description,
        "safety_level": tool.safety_level,
        "category": tool_registry._get_tool_category(tool.name),
        "schema": tool.get_schema(),
    }


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
@router.post("/execute")
@router.post("/v2/execute")
async def execute_tool(request: ToolExecutionRequest) -> dict:
    result = await tool_registry.execute_tool(
        request.tool_name,
        request.parameters,
        skip_safety_check=request.skip_safety_check,
    )
    payload = result.to_dict()
    if request.session_id and result.context_updates:
        context_manager.update_context(request.session_id, result.context_updates)
    return payload


@router.post("/verify")
async def verify_tool_result(request: VerificationRequest) -> VerificationResponse:
    from app.tools.terminal_base import ToolResult

    result = ToolResult(**{k: v for k, v in request.result.items() if k in (
        "success", "message", "output", "error", "exit_code", "data",
        "verification_passed", "context_updates", "tool", "error_code",
    )})
    verified = await tool_registry.verify_tool_result(request.tool_name, result, request.parameters)
    return VerificationResponse(
        verified=verified,
        details="Verification passed" if verified else "Verification failed",
    )


# ---------------------------------------------------------------------------
# Context (session-scoped)
# ---------------------------------------------------------------------------
@router.get("/context")
async def get_context(session_id: Optional[str] = Query(None)) -> dict:
    sid = _resolve_session_id(session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail="No active session. Connect the WebSocket or pass ?session_id=")
    snapshot = context_manager.get_context_snapshot(sid)
    if snapshot is None:
        snapshot = {"session_id": sid}
    return snapshot


@router.get("/context/summary")
async def get_context_summary(session_id: Optional[str] = Query(None)) -> dict:
    sid = _resolve_session_id(session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail="No active session. Connect the WebSocket or pass ?session_id=")
    summary = context_manager.get_context_summary(sid)
    return {"session_id": sid, "summary": summary, "has_context": bool(summary)}


@router.post("/context/update")
async def update_context(request: ContextUpdateRequest) -> dict:
    sid = request.session_id or _resolve_session_id(None)
    if sid is None:
        raise HTTPException(status_code=404, detail="No active session.")
    context_manager.update_context(sid, request.updates)
    return {"success": True, "session_id": sid, "message": "Context updated"}


@router.post("/context/reset")
async def reset_context(request: ContextUpdateRequest) -> dict:
    sid = request.session_id or _resolve_session_id(None)
    if sid is None:
        raise HTTPException(status_code=404, detail="No active session.")
    context_manager.reset(sid)
    return {"success": True, "session_id": sid, "message": "Context reset"}


# ---------------------------------------------------------------------------
# Intent / status / capabilities
# ---------------------------------------------------------------------------
@router.post("/intent/analyze")
async def analyze_intent(request: IntentAnalysisRequest) -> dict:
    context: Dict[str, object] = {}
    sid = request.session_id or _resolve_session_id(None)
    if sid:
        snapshot = context_manager.get_context_snapshot(sid) or {}
        context.update(snapshot)
    if request.context:
        context.update(request.context)

    recommended = tool_registry.get_recommended_tools(request.command, context)
    return {
        "intent_type": "task",
        "recommended_tools": recommended,
        "context_aware": bool(sid),
        "command": request.command,
        "session_id": sid,
    }


@router.post("/recommend", response_model=ToolRecommendationResponse)
async def recommend_tools(request: ToolRecommendationRequest) -> ToolRecommendationResponse:
    recommended = tool_registry.get_recommended_tools(request.intent, request.context or {})
    return ToolRecommendationResponse(
        recommendations=[
            ToolRecommendation(
                tool_name=name,
                confidence=0.8,
                reasoning=f"Recommended for intent: {request.intent}",
            )
            for name in recommended
        ],
        context_used=bool(request.context),
    )


@router.get("/status", response_model=SystemStatus)
async def get_system_status(session_id: Optional[str] = Query(None)) -> SystemStatus:
    sid = _resolve_session_id(session_id)
    state = "idle"
    last_action = None
    context_active = False
    if sid:
        session = session_manager.get(sid)
        if session:
            state = session.state_machine.get_current_state().value
            context = context_manager.get_context(sid)
            if context:
                context_active = True
                if context.recent_actions:
                    last_action = context.recent_actions[-1].tool
    return SystemStatus(
        state=state,
        tools_available=len(tool_registry.get_all_tools()),
        context_active=context_active,
        continuous_listening=True,
        last_action=last_action,
        uptime_seconds=time.time() - START_TIME,
        session_id=sid,
    )


# ---------------------------------------------------------------------------
# Local intelligence (Phase 1/3): status, train, corrections
# ---------------------------------------------------------------------------
@router.get("/intelligence/status")
async def intelligence_status() -> dict:
    """Local-brain model + outcome stats (what the settings UI should show)."""
    from app.intelligence.brain import get_brain

    brain = get_brain()
    try:
        brain.ensure_model()
    except Exception:  # noqa: BLE001
        pass
    accuracy = brain.memory.get_model_meta("intent_model_accuracy")
    try:
        return {
            "engine": "local (TF-IDF + scikit-learn linear classifier)",
            "model_loaded": brain.classifier.is_trained(),
            "intent_classes": len(brain.classifier.labels),
            "confidence_threshold": brain.classifier.confidence_threshold,
            "outcomes": brain.outcome_stats(),
            "accuracy": accuracy,
            "model_path": brain.classifier.model_path,
        }
    except Exception as e:  # noqa: BLE001
        return {"engine": "local", "error": str(e)}


@router.post("/intelligence/train")
async def intelligence_train() -> dict:
    """Re-train the local intent model from the corpus + stored corrections."""
    from app.intelligence.brain import get_brain

    brain = get_brain()
    try:
        metrics = brain.train_and_evaluate()
        return {"success": True, "accuracy": metrics.get("accuracy"),
                "f1_macro": metrics.get("f1_macro"),
                "train_samples": metrics.get("train_samples"),
                "test_samples": metrics.get("test_samples"),
                "outcomes": brain.outcome_stats()}
    except Exception as e:  # noqa: BLE001
        logger.error("intelligence_train_error", error=str(e))
        return {"success": False, "message": str(e)}


@router.get("/intelligence/actions")
async def intelligence_actions(limit: int = 50) -> dict:
    """Recent recorded actions (persistent memory, for diagnostics)."""
    from app.intelligence.brain import get_brain

    return {"actions": get_brain().recent_actions(limit)}


@router.get("/platform")
async def get_platform_info() -> dict:
    """Report the active platform adapter + its supported capabilities.

    This is the seam that lets the SAME core intelligence run on Linux, Windows
    and (where supported) Android with separate OS adapters.
    """
    from app.platform import get_platform_capabilities

    return get_platform_capabilities()


@router.get("/capabilities", response_model=SystemCapabilities)
async def get_capabilities() -> SystemCapabilities:
    info = tool_registry.get_tool_info()
    return SystemCapabilities(
        level=1,
        features=[
            "Terminal-first desktop control",
            "Application management",
            "File operations",
            "System control (screenshot, volume, clipboard)",
            "Real browser automation",
            "Context awareness",
            "Continuous listening",
            "Action verification",
        ],
        tools_by_category=info["categories"],
        continuous_listening=True,
        context_awareness=True,
        verification_enabled=True,
    )
