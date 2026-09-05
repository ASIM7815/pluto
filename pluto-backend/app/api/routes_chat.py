"""Chat and command execution routes"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from app.schemas.chat import CommandRequest, CommandResponse, AgentStateEvent
from app.agent.orchestrator import agent_orchestrator
from app.core.logging import get_logger
import json

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/execute")
async def execute_command(request: CommandRequest) -> CommandResponse:
    """Execute a command (non-streaming)"""
    try:
        logger.info("command_received", command=request.command)
        
        # Collect all events
        events = []
        async for event in agent_orchestrator.execute_command(request.command, request.context):
            events.append(event)
        
        # Return final state
        final_event = events[-1] if events else None
        
        return CommandResponse(
            success=final_event.state != "error" if final_event else False,
            message=final_event.task or "Command processed",
            state=final_event.state or "idle",
            data=final_event.data if final_event else None
        )
        
    except Exception as e:
        logger.error("command_error", error=str(e))
        return CommandResponse(
            success=False,
            message=str(e),
            state="error"
        )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time agent communication"""
    await websocket.accept()
    logger.info("websocket_connected")
    
    try:
        while True:
            # Receive command from frontend
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "command":
                command = message.get("command", "")
                
                # Stream events back to frontend
                async for event in agent_orchestrator.execute_command(command):
                    await websocket.send_json(event.dict())
            
            elif message.get("type") == "reset":
                agent_orchestrator.reset()
                await websocket.send_json({
                    "type": "agent_state",
                    "state": "idle"
                })
    
    except WebSocketDisconnect:
        logger.info("websocket_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e))


@router.post("/reset")
async def reset_agent():
    """Reset agent conversation history"""
    agent_orchestrator.reset()
    return {"message": "Agent reset successfully"}
