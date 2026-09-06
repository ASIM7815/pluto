"""API endpoints for PLUTO Level 1 tool system and context management"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.schemas.tools import (
    ToolInfo,
    ToolRegistryInfo,
    ToolExecutionRequest,
    ToolExecutionResult,
    ContextSummary,
    ContextUpdateRequest,
    IntentAnalysisRequest,
    IntentAnalysisResponse,
    UserIntent,
    ToolRecommendationRequest,
    ToolRecommendationResponse,
    ToolRecommendation,
    VerificationRequest,
    VerificationResponse,
    SystemStatus,
    SystemCapabilities,
)
from app.tools.registry import get_registry
from app.agent.context_manager import ContextManager
from app.agent.state_machine import StateMachine
from app.core.logging import get_logger
import time

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])

# Global instances
tool_registry = get_registry()
context_manager = ContextManager()
state_machine = StateMachine()

# Track uptime
START_TIME = time.time()


@router.get("/registry", response_model=Dict[str, Any])
async def get_tool_registry():
    """Get information about all registered tools"""
    try:
        info = tool_registry.get_tool_info()
        logger.info("tool_registry_fetched", total_tools=info["total_tools"])
        return info
    except Exception as e:
        logger.error("tool_registry_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools", response_model=List[Dict[str, Any]])
async def list_tools(category: str = None):
    """List all tools, optionally filtered by category"""
    try:
        if category:
            tools = tool_registry.get_tools_by_category(category)
        else:
            tools = tool_registry.get_all_tools()
        
        tool_list = [
            {
                "name": tool.name,
                "description": tool.description,
                "safety_level": tool.safety_level,
                "category": tool_registry._get_tool_category(tool.name)
            }
            for tool in tools
        ]
        
        logger.info("tools_listed", count=len(tool_list), category=category)
        return tool_list
    except Exception as e:
        logger.error("tools_list_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/{tool_name}", response_model=Dict[str, Any])
async def get_tool_details(tool_name: str):
    """Get details for a specific tool"""
    try:
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        
        schema = tool.get_schema()
        return {
            "name": tool.name,
            "description": tool.description,
            "safety_level": tool.safety_level,
            "category": tool_registry._get_tool_category(tool.name),
            "schema": schema
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("tool_details_error", tool=tool_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=Dict[str, Any])
async def execute_tool(request: ToolExecutionRequest):
    """Execute a tool (for testing/debugging)"""
    try:
        result = await tool_registry.execute_tool(
            request.tool_name,
            request.parameters,
            skip_safety_check=request.skip_safety_check
        )
        
        return {
            "success": result.success,
            "message": result.message,
            "output": result.output,
            "error": result.error,
            "data": result.data,
            "verification_passed": result.verification_passed,
            "context_updates": result.context_updates
        }
    except Exception as e:
        logger.error("tool_execution_error", tool=request.tool_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=VerificationResponse)
async def verify_tool_result(request: VerificationRequest):
    """Verify a tool execution result"""
    try:
        # Convert dict to ToolResult (simplified)
        from app.tools.terminal_base import ToolResult
        result = ToolResult(
            success=request.result.success,
            message=request.result.message,
            output=request.result.output,
            error=request.result.error,
            exit_code=request.result.exit_code,
            data=request.result.data,
            verification_passed=request.result.verification_passed,
            context_updates=request.result.context_updates
        )
        
        verified = await tool_registry.verify_tool_result(
            request.tool_name,
            result,
            request.parameters
        )
        
        return VerificationResponse(
            verified=verified,
            details="Verification passed" if verified else "Verification failed"
        )
    except Exception as e:
        logger.error("verification_error", tool=request.tool_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context", response_model=Dict[str, Any])
async def get_context():
    """Get current session context"""
    try:
        context = context_manager.get_context()
        return {
            "current_app": context.current_app,
            "active_window": context.active_window,
            "current_directory": context.current_directory,
            "browser_url": context.browser_url,
            "browser_title": context.browser_title,
            "recent_actions_count": len(context.recent_actions),
            "recent_files_count": len(context.recent_files)
        }
    except Exception as e:
        logger.error("context_fetch_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/summary", response_model=Dict[str, Any])
async def get_context_summary():
    """Get human-readable context summary"""
    try:
        summary = context_manager.get_context_summary()
        return {
            "summary": summary,
            "context": context_manager.get_context()
        }
    except Exception as e:
        logger.error("context_summary_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context/update")
async def update_context(request: ContextUpdateRequest):
    """Update session context"""
    try:
        context_manager.update_context(request.updates)
        return {"success": True, "message": "Context updated"}
    except Exception as e:
        logger.error("context_update_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context/reset")
async def reset_context():
    """Reset session context"""
    try:
        context_manager.reset()
        return {"success": True, "message": "Context reset"}
    except Exception as e:
        logger.error("context_reset_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intent/analyze", response_model=Dict[str, Any])
async def analyze_intent(request: IntentAnalysisRequest):
    """Analyze user intent and recommend tools"""
    try:
        # Get context if available
        context = request.context or context_manager.get_context().__dict__
        
        # Get recommended tools
        recommended = tool_registry.get_recommended_tools(request.command, context)
        
        # Simple intent detection (can be enhanced with NLP)
        intent_type = "other"
        if any(word in request.command.lower() for word in ["open", "launch", "start"]):
            intent_type = "open_app"
        elif any(word in request.command.lower() for word in ["close", "quit"]):
            intent_type = "close_app"
        elif any(word in request.command.lower() for word in ["find", "search"]):
            intent_type = "find_file" if "file" in request.command.lower() else "search"
        elif "screenshot" in request.command.lower():
            intent_type = "screenshot"
        elif any(word in request.command.lower() for word in ["volume", "sound"]):
            intent_type = "volume_control"
        elif "silence" in request.command.lower():
            intent_type = "silence"
        
        return {
            "intent_type": intent_type,
            "recommended_tools": recommended,
            "context_aware": bool(context),
            "command": request.command
        }
    except Exception as e:
        logger.error("intent_analysis_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend", response_model=ToolRecommendationResponse)
async def recommend_tools(request: ToolRecommendationRequest):
    """Get tool recommendations for a given intent"""
    try:
        context = request.context or context_manager.get_context().__dict__
        recommended = tool_registry.get_recommended_tools(request.intent, context)
        
        recommendations = [
            ToolRecommendation(
                tool_name=tool_name,
                confidence=0.8,  # Simplified confidence score
                reasoning=f"Recommended for intent: {request.intent}"
            )
            for tool_name in recommended
        ]
        
        return ToolRecommendationResponse(
            recommendations=recommendations,
            context_used=bool(context)
        )
    except Exception as e:
        logger.error("recommendation_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current system status"""
    try:
        current_state = state_machine.get_current_state()
        last_action = None
        if context_manager.get_context().recent_actions:
            last_action = context_manager.get_context().recent_actions[-1].tool
        
        return SystemStatus(
            state=current_state.value,
            tools_available=len(tool_registry.get_all_tools()),
            context_active=True,
            continuous_listening=True,
            last_action=last_action,
            uptime_seconds=time.time() - START_TIME
        )
    except Exception as e:
        logger.error("status_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities", response_model=SystemCapabilities)
async def get_capabilities():
    """Get system capabilities"""
    try:
        info = tool_registry.get_tool_info()
        
        return SystemCapabilities(
            level=1,  # Level 1: Desktop Control
            features=[
                "Terminal-first desktop control",
                "Application management",
                "File operations",
                "System control (screenshot, volume, clipboard)",
                "Context awareness",
                "Continuous listening",
                "Action verification"
            ],
            tools_by_category=info["categories"],
            continuous_listening=True,
            context_awareness=True,
            verification_enabled=True
        )
    except Exception as e:
        logger.error("capabilities_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
