"""Chat & command routes: the WebSocket hub driving the agent loop.

WebSocket protocol (all events are JSON):

Client -> server:
    { "type": "command", "command": "Open YouTube" }
    { "type": "confirm", "action": "delete_file" }
    { "type": "reject",  "action": "delete_file" }
    { "type": "interrupt" }
    { "type": "reset", "clearHistory": true }

Server -> client (initial):
    { "type": "session", "session_id": "abc123", "state": "idle" }

Server -> client (during a task): the agent_state / execution_step /
activity / action_preview / speak / error events from the orchestrator, always
ending with state "listening" (or an error + recovery to listening).

A client may connect with ``/ws?session_id=...`` so the same session id is used
across WebSocket + REST fallback + context endpoints.
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.agent.orchestrator import agent_orchestrator
from app.agent.session_manager import session_manager
from app.agent.state_machine import PlutoState
from app.core.logging import get_logger
from app.schemas.chat import (
    AgentStateEvent,
    CommandRequest,
    CommandResponse,
    ConfirmRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

SILENCE_KEYWORDS = ["silence", "stop listening", "be quiet", "shut up", "stop talking", "be silent", "go silent"]

# Bare phrases that mean "abort what you're doing" - only when they arrive as
# the ENTIRE command ("stop" interrupts, but "stop the music" is a real task).
INTERRUPT_PHRASES = {
    "stop", "stop it", "stop pluto", "cancel", "abort", "never mind", "nevermind",
    "quiet", "silence", "shut up", "stop talking", "stop speaking", "be quiet",
    "go to sleep", "sleep",
}


class ResetRequest(BaseModel):
    session_id: Optional[str] = None
    clearHistory: bool = True


# ---------------------------------------------------------------------------
# REST (non-streaming) fallback - shares the session/context with the WS hub
# ---------------------------------------------------------------------------
@router.post("/execute", response_model=CommandResponse)
async def execute_command(request: CommandRequest) -> CommandResponse:
    """Execute a command without streaming; uses the provided session id."""
    sid = request.session_id
    session = session_manager.get(sid) if sid else None
    if session is None:
        # Let the orchestrator create/register the session.
        sid = sid or None
    elif session.is_busy:
        return CommandResponse(
            success=False, message="PLUTO is busy with another command.",
            state="error", session_id=session.id,
        )
    try:
        logger.info("command_rest", command=request.command, session=sid)
        response = await agent_orchestrator.execute_command(
            request.command, request.context, session_id=sid
        )
        return response
    except Exception as e:  # noqa: BLE001
        logger.error("command_error", error=str(e))
        return CommandResponse(success=False, message=str(e), state="error", session_id=sid)


@router.post("/confirm")
async def confirm_action(request: ConfirmRequest) -> dict:
    """Approve/reject a pending action for a session."""
    session = session_manager.get(request.session_id) if request.session_id else None
    if session is None:
        active = session_manager.active_sessions()
        session = session_manager.get(active[0]) if active else None
    if session is None:
        return {"message": "No active session.", "approved": False}
    if session.pending_action:
        session.confirm(approved=request.approved)
        await session.push(AgentStateEvent(
            type="agent_state",
            state="executing" if request.approved else "idle",
            task="Confirmed, continuing..." if request.approved else "Action cancelled.",
            session_id=session.id,
        ))
        return {"message": "Approved" if request.approved else "Rejected",
                "approved": request.approved, "session_id": session.id}
    return {"message": "No action is waiting for confirmation.",
            "approved": False, "session_id": session.id}


@router.post("/reset")
async def reset_agent(request: ResetRequest) -> dict:
    """Reset a session (cancel task, clear history & context)."""
    from app.agent.context_manager import context_manager
    if request.session_id:
        session = session_manager.get(request.session_id)
        if session:
            session.reset(clear_history=request.clearHistory)
            context_manager.reset(session.id)
            return {"message": "Session reset", "session_id": session.id}
        return {"message": "Session not found", "session_id": request.session_id}
    # Legacy: reset all sessions.
    for sid in list(session_manager.active_sessions()):
        session = session_manager.get(sid)
        if session:
            session.reset(clear_history=request.clearHistory)
            context_manager.reset(sid)
    agent_orchestrator.reset()
    return {"message": "All sessions reset"}


# ---------------------------------------------------------------------------
# WebSocket hub
# ---------------------------------------------------------------------------
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    requested_id = websocket.query_params.get("session_id", "").strip() or None
    existing = session_manager.get(requested_id) if requested_id else None

    if existing is not None and not existing.is_busy and not existing.state_machine.is_busy():
        session = existing
        session.queue = asyncio.Queue()  # drop events from a previous socket
    else:
        session = session_manager.create_session(requested_id)

    session.confirmation_available = True  # type: ignore[attr-defined]
    logger.info("websocket_connected", session=session.id)

    # Announce the session so the frontend knows the id for REST/context calls.
    await websocket.send_json(AgentStateEvent(
        type="session",
        session_id=session.id,
        state=session.state_machine.get_current_state().value,
        task="Connected. Ready for your command.",
    ).model_dump())

    async def sender() -> None:
        try:
            while True:
                event = await session.queue.get()
                await websocket.send_json(event.model_dump())
        except Exception:  # noqa: BLE001 - socket closed / sender cancelled
            pass

    sender_task = asyncio.create_task(sender())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("ws_invalid_json", session=session.id)
                continue

            mtype = message.get("type")
            if mtype == "command":
                command = str(message.get("command", "")).strip()
                if not command:
                    continue
                logger.info("command_ws", command=command, session=session.id)
                normalized = command.lower().strip(" .!,?")
                is_silence = any(k in command.lower() for k in SILENCE_KEYWORDS)
                if is_silence or normalized in INTERRUPT_PHRASES:
                    was_busy = session.is_busy or session.state_machine.is_busy()
                    if was_busy:
                        # Voice barge-in: abort the running task & speech.
                        session.interrupt()
                        await session.push(AgentStateEvent(
                            type="agent_state", state="idle",
                            task="Stopped, BOSS.", data={"response": "Stopped, BOSS."},
                            session_id=session.id,
                        ))
                    else:
                        await session.push(AgentStateEvent(
                            type="agent_state", state="idle",
                            task="Going silent.", data={"response": "Going silent."},
                            session_id=session.id,
                        ))
                        await session.push(AgentStateEvent(
                            type="silence", state="idle",
                            task="Silence mode activated", session_id=session.id,
                        ))
                else:
                    session_manager.submit_command(session, command)

            elif mtype == "confirm":
                if session.pending_action:
                    session.confirm(approved=True)
                    await session.push(AgentStateEvent(
                        type="agent_state", state="executing",
                        task="Confirmed, continuing...", session_id=session.id,
                    ))
                else:
                    logger.info("confirm_without_pending", session=session.id)

            elif mtype == "reject":
                if session.pending_action:
                    session.confirm(approved=False)
                else:
                    logger.info("reject_without_pending", session=session.id)

            elif mtype == "interrupt":
                session.interrupt()
                await session.push(AgentStateEvent(
                    type="agent_state", state="idle", task="Stopped.", session_id=session.id,
                ))

            elif mtype == "reset":
                clear = bool(message.get("clearHistory", True))
                session.reset(clear_history=clear)
                await session.push(AgentStateEvent(
                    type="agent_state", state="idle", task="Conversation reset.",
                    session_id=session.id,
                ))

            elif mtype == "ping":
                await session.push(AgentStateEvent(
                    type="agent_state", state=session.state_machine.get_current_state().value,
                    session_id=session.id,
                ))

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", session=session.id)
    except Exception as e:  # noqa: BLE001
        logger.error("websocket_error", error=str(e), session=session.id)
    finally:
        if not sender_task.done():
            sender_task.cancel()
        # Reset confirmation availability flag if the object stays cached.
        session.confirmation_available = False  # type: ignore[attr-defined]
        if session.state_machine.get_current_state() in (PlutoState.IDLE, PlutoState.LISTENING):
            session_manager.remove(session.id)
        # If a task is still running, keep the session so events/history remain
        # coherent, but it will be pruned once idle (see SessionManager).
