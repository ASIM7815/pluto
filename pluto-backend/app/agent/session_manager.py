"""Per-connection session state for the agent loop.

A session owns:
  - an asyncio.Queue of events to be streamed back to the WebSocket,
  - persistent conversation history (context),
  - a pending-action gate so a command can pause on confirmation and resume
    when the user approves/rejects it,
  - an interrupt signal so a running task can be cancelled,
  - the running asyncio.Task for the current command.

This lets the WebSocket loop keep receiving `confirm` / `reject` / `interrupt`
messages while a command is suspended waiting for permission.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.schemas.chat import AgentStateEvent

logger = get_logger(__name__)


class Session:
    """State for one connected WebSocket client."""

    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.queue: asyncio.Queue[AgentStateEvent] = asyncio.Queue()
        self.history: List[Dict] = []
        self.running: bool = False
        self.current_task: Optional[asyncio.Task] = None
        self.pending_action: Optional[str] = None
        self._confirm_event = asyncio.Event()
        self._approved: bool = True
        self._interrupt_event = asyncio.Event()

    # ---- confirmation gating ----
    def require_confirmation(self, action: str) -> None:
        self.pending_action = action
        self._confirm_event.clear()
        self._approved = False

    async def wait_for_confirmation(self) -> bool:
        """Suspend until the user confirms or rejects the pending action."""
        await self._confirm_event.wait()
        return self._approved

    def confirm(self, approved: bool) -> None:
        self._approved = approved
        self.pending_action = None
        self._confirm_event.set()

    # ---- interrupt ----
    def interrupt(self) -> None:
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    def reset(self, clear_history: bool = True) -> None:
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        self.running = False
        self.pending_action = None
        self._interrupt_event.set()
        if clear_history:
            self.history = []

    async def push(self, event: AgentStateEvent) -> None:
        await self.queue.put(event)


class SessionManager:
    """Registry of active sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create_session(self) -> Session:
        sid = uuid.uuid4().hex[:8]
        session = Session(sid)
        self._sessions[sid] = session
        logger.info("session_created", session=sid)
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def submit_command(self, session: Session, command: str) -> None:
        """Start a background task running the agent loop for this command."""
        if session.current_task and not session.current_task.done():
            # A task is already running; queue it instead of overloading.
            logger.warning("command_queued_busy", session=session.id)
            session.queue.put_nowait(AgentStateEvent(
                type="agent_state",
                state="error",
                error="PLUTO is still busy — try again in a moment.",
                task="Busy",
            ))
            return
        from app.agent.orchestrator import agent_orchestrator  # lazy import
        session._interrupt_event.clear()
        session.current_task = asyncio.create_task(
            agent_orchestrator.process_command(session, command)
        )
        session.current_task.add_done_callback(lambda _t: setattr(session, "current_task", None))
        session.running = True


session_manager = SessionManager()
