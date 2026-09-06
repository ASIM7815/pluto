"""Per-session state for the agent loop.

A Session owns:
  - a unique ``session_id`` that is ALSO the ContextManager key, so context,
    conversation history, voice and the frontend all refer to the same session,
  - an asyncio.Queue of events streamed back to the client,
  - the persistent conversation history,
  - a per-session StateMachine (concurrent sessions never share state),
  - a pending-action gate so a command can pause on confirmation,
  - an interrupt signal, and the running asyncio.Task for the current command.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.agent.state_machine import StateMachine, PlutoState
from app.core.logging import get_logger
from app.schemas.chat import AgentStateEvent

logger = get_logger(__name__)

MAX_SESSIONS = 64


class Session:
    """State for one PLUTO session (one connected client or REST flow)."""

    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.queue: asyncio.Queue[AgentStateEvent] = asyncio.Queue()
        self.history: List[Dict] = []
        self.state_machine = StateMachine()
        self.running: bool = False
        self.current_task: Optional[asyncio.Task] = None
        self.pending_action: Optional[str] = None
        self._confirm_event = asyncio.Event()
        self._approved: bool = True
        # True when a human is attached and can approve actions (WebSocket).
        # The REST fallback sets this to False: confirmation-gated tools then
        # report cancellation honestly instead of hanging forever.
        self.confirmation_available: bool = True
        self.created_at: datetime = datetime.now()
        self.last_activity: datetime = datetime.now()

    # ------------------------------------------------------------------
    # Confirmation gating
    # ------------------------------------------------------------------
    def require_confirmation(self, action: str) -> None:
        self.pending_action = action
        self._confirm_event.clear()
        self._approved = False

    async def wait_for_confirmation(self) -> bool:
        await self._confirm_event.wait()
        return self._approved

    def confirm(self, approved: bool) -> None:
        self._approved = approved
        self.pending_action = None
        self._confirm_event.set()

    # ------------------------------------------------------------------
    # Interrupt / lifecycle
    # ------------------------------------------------------------------
    def interrupt(self) -> None:
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    def reset(self, clear_history: bool = True) -> None:
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        self.running = False
        self.pending_action = None
        if clear_history:
            self.history = []
        self.state_machine.reset()

    def touch(self) -> None:
        self.last_activity = datetime.now()

    async def push(self, event: AgentStateEvent) -> None:
        self.last_activity = datetime.now()
        await self.queue.put(event)

    @property
    def is_busy(self) -> bool:
        return bool(self.current_task and not self.current_task.done())

    def status_dict(self) -> dict:
        return {
            "session_id": self.id,
            "state": self.state_machine.get_current_state().value,
            "busy": self.is_busy,
            "history_len": len(self.history),
            "pending_action": self.pending_action,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }


class SessionManager:
    """Registry of active sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    # ------------------------------------------------------------------
    def create_session(self, session_id: Optional[str] = None) -> Session:
        """Create a new session with a unique id (or the provided one if free)."""
        sid = session_id or uuid.uuid4().hex[:12]
        # If the id is already taken, fall back to a fresh unique id.
        if sid in self._sessions:
            sid = uuid.uuid4().hex[:12]
        session = Session(sid)
        self._sessions[sid] = session
        self._prune()
        logger.info("session_created", session=sid)
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> Session:
        """Resolve an existing session or create one for the given id.

        A session id supplied by a client (e.g. across REST calls) must never
        be hard-coded by the server; we simply honour the client-generated id.
        """
        session = self.get(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session

    def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.is_busy:
            session.interrupt()
        if session is not None:
            logger.info("session_removed", session=session_id)

    def active_sessions(self) -> List[str]:
        return list(self._sessions.keys())

    def status_list(self) -> List[dict]:
        return [s.status_dict() for s in self._sessions.values()]

    def submit_command(self, session: Session, command: str) -> bool:
        """
        Start the agent loop for a command on a session.

        Returns True when the command was accepted, False when the session was
        busy (an error event is queued in that case).
        """
        if session.is_busy:
            logger.warning("command_busy", session=session.id)
            session.queue.put_nowait(AgentStateEvent(
                type="agent_state",
                state="error",
                error="PLUTO is still working on the previous command. Please wait a moment.",
                task="Busy",
            ))
            return False

        from app.agent.pattern_orchestrator import pattern_orchestrator as agent_orchestrator  # lazy import
        session.running = True
        session.touch()
        session.current_task = asyncio.create_task(
            agent_orchestrator.process_command(session, command)
        )
        session.current_task.add_done_callback(
            lambda _t: self._on_task_done(session)
        )
        return True

    def _on_task_done(self, session: Session) -> None:
        session.current_task = None
        session.running = False
        session.touch()

    def _prune(self) -> None:
        """Evict idle, non-running sessions when over the cap."""
        if len(self._sessions) <= MAX_SESSIONS:
            return
        # Oldest-first, never evict running sessions.
        idle = sorted(
            (s for s in self._sessions.values() if not s.is_busy),
            key=lambda s: s.last_activity,
        )
        overflow = len(self._sessions) - MAX_SESSIONS
        for session in idle[:overflow]:
            self.remove(session.id)


# Canonical singleton.
session_manager = SessionManager()
