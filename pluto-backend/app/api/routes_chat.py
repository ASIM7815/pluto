"""Chat & command routes: the WebSocket hub driving the agent loop."""
import asyncio
import json
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.agent.orchestrator import agent_orchestrator
from app.agent.session_manager import session_manager
from app.core.logging import get_logger
from app.schemas.chat import (
    AgentStateEvent,
    CommandRequest,
    CommandResponse,
    ConfirmRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# REST (non-streaming) fallback
# ---------------------------------------------------------------------------
@router.post("/execute")
async def execute_command(request: CommandRequest) -> CommandResponse:
    """Execute a command (non-streaming)."""
    try:
        logger.info("command_received", command=request.command)
        events: List[AgentStateEvent] = []
        async for event in agent_orchestrator.execute_command(request.command, request.context):
            events.append(event)
        final = events[-1] if events else None
        return CommandResponse(
            success=bool(final and final.state != "error"),
            message=(final.task or "Command processed") if final else "Command processed",
            state=(final.state or "idle") if final else "idle",
            data=(final.data or None) if final else None,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("command_error", error=str(e))
        return CommandResponse(success=False, message=str(e), state="error")


@router.post("/confirm")
async def confirm_action(request: ConfirmRequest) -> dict:
    """Approve/reject a pending action (REST convenience)."""
    # Confirmations are primarily handled over WebSocket; this is a fallback.
    return {"message": "Use the WebSocket for confirmations.", "approved": request.approved}


@router.post("/reset")
async def reset_agent() -> dict:
    """Reset conversation history."""
    agent_orchestrator.reset()
    return {"message": "Agent reset successfully"}


# ---------------------------------------------------------------------------
# WebSocket hub
# ---------------------------------------------------------------------------
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = session_manager.create_session()
    logger.info("websocket_connected", session=session.id)

    async def sender() -> None:
        """Drain the session event queue and push to the frontend."""
        try:
            while True:
                event = await session.queue.get()
                await websocket.send_json(event.model_dump())
        except Exception:  # noqa: BLE001
            # Socket closed or sender cancelled.
            pass

    sender_task = asyncio.create_task(sender())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = message.get("type")
            if mtype == "command":
                command = message.get("command", "").strip()
                if command:
                    # Check for silence/stop commands
                    silence_keywords = ["silence", "stop listening", "be quiet", "shut up", "stop talking", "be silent"]
                    if any(keyword in command.lower() for keyword in silence_keywords):
                        logger.info("silence_command", session=session.id)
                        await session.queue.put(AgentStateEvent(
                            type="agent_state",
                            state="idle",
                            task="Going silent.",
                            data={"response": "Going silent."}
                        ))
                        # Send a special "silence" event to tell frontend to stop listening
                        await session.queue.put(AgentStateEvent(
                            type="silence",
                            state="idle",
                            task="Silence mode activated"
                        ))
                    else:
                        logger.info("command_ws", command=command, session=session.id)
                        session_manager.submit_command(session, command)

            elif mtype == "confirm":
                action = message.get("action", "")
                session.confirm(approved=True)
                await session.queue.put(AgentStateEvent(
                    type="agent_state",
                    state="executing",
                    task=f"Confirmed '{action}', executing...",
                ))

            elif mtype == "reject":
                session.confirm(approved=False)
                # The orchestrator reports the cancellation/return-to-listening.

            elif mtype == "interrupt":
                session.interrupt()
                await session.queue.put(AgentStateEvent(
                    type="agent_state", state="idle", task="Stopped."
                ))

            elif mtype == "reset":
                clear = message.get("clearHistory", True)
                session.reset(clear_history=clear)
                await session.queue.put(AgentStateEvent(
                    type="agent_state", state="idle", task="Conversation reset."
                ))

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", session=session.id)
    except Exception as e:  # noqa: BLE001
        logger.error("websocket_error", error=str(e), session=session.id)
    finally:
        if not sender_task.done():
            sender_task.cancel()
        session_manager.remove(session.id)
