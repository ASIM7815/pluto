"""PLUTO State Machine - manages autonomous agent states and transitions.

Canonical states (mirror of schemas/chat.PlutoState + frontend):

    IDLE -> LISTENING -> UNDERSTANDING -> THINKING -> PLANNING -> EXECUTING
    EXECUTING -> VERIFYING -> THINKING (another tool pass) | SPEAKING
    SPEAKING -> SUCCESS -> LISTENING (loop continues)
    ERROR -> LISTENING | IDLE

A fresh StateMachine is created per Session so concurrent sessions can never
corrupt each other's state.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class PlutoState(str, Enum):
    """All possible PLUTO states."""

    IDLE = "idle"                    # Waiting / ready, no task in flight
    LISTENING = "listening"          # Recording / awaiting voice input
    UNDERSTANDING = "understanding"  # Parsing the natural-language request
    THINKING = "thinking"            # LLM analyzing intent / next step
    PLANNING = "planning"            # Breaking the task into tool steps
    EXECUTING = "executing"          # Running a tool/action
    VERIFYING = "verifying"          # Checking an executed action actually happened
    OBSERVING = "observing"          # Reading the tool observation
    REASONING = "reasoning"          # Deciding the next step from the observation
    SPEAKING = "speaking"            # Voice response is being produced
    SUCCESS = "success"              # Task completed successfully
    ERROR = "error"                  # Task failed / aborted


# States which mean "PLUTO is doing something right now".
_BUSY_STATES = {
    PlutoState.UNDERSTANDING,
    PlutoState.THINKING,
    PlutoState.PLANNING,
    PlutoState.EXECUTING,
    PlutoState.VERIFYING,
    PlutoState.OBSERVING,
    PlutoState.REASONING,
    PlutoState.SPEAKING,
}

#: Canonical happy-path task cycle, used by orchestrator when it needs to
#: "reset to listening" in one step.
TASK_FLOW = [
    PlutoState.LISTENING,
    PlutoState.UNDERSTANDING,
    PlutoState.THINKING,
    PlutoState.PLANNING,
    PlutoState.EXECUTING,
    PlutoState.VERIFYING,
    PlutoState.OBSERVING,
    PlutoState.REASONING,
    PlutoState.SPEAKING,
    PlutoState.SUCCESS,
]


class StateTransition:
    """A recorded state transition."""

    def __init__(
        self,
        from_state: PlutoState,
        to_state: PlutoState,
        timestamp: datetime,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.timestamp = timestamp
        self.reason = reason
        self.metadata = metadata or {}


class StateMachine:
    """
    PLUTO State Machine.

    Tracks the current state, validates transitions, and keeps a history for
    debugging. Transition validation is strict for the *normal* task cycle;
    ERROR can always lead back to IDLE/LISTENING, and ``force=True`` exists for
    recovery paths so an invalid intermediate state can never wedge the agent.
    """

    VALID_TRANSITIONS: Dict[PlutoState, List[PlutoState]] = {
        PlutoState.IDLE: [PlutoState.LISTENING, PlutoState.UNDERSTANDING, PlutoState.ERROR],
        PlutoState.LISTENING: [PlutoState.IDLE, PlutoState.UNDERSTANDING, PlutoState.ERROR],
        PlutoState.UNDERSTANDING: [PlutoState.THINKING, PlutoState.LISTENING, PlutoState.ERROR],
        PlutoState.THINKING: [
            PlutoState.PLANNING, PlutoState.SPEAKING, PlutoState.LISTENING, PlutoState.ERROR,
        ],
        PlutoState.PLANNING: [PlutoState.EXECUTING, PlutoState.SPEAKING, PlutoState.LISTENING, PlutoState.ERROR],
        PlutoState.EXECUTING: [PlutoState.VERIFYING, PlutoState.ERROR],
        PlutoState.VERIFYING: [
            PlutoState.OBSERVING, PlutoState.THINKING, PlutoState.SPEAKING,
            PlutoState.EXECUTING, PlutoState.LISTENING, PlutoState.ERROR,
        ],
        PlutoState.OBSERVING: [PlutoState.REASONING, PlutoState.LISTENING, PlutoState.ERROR],
        PlutoState.REASONING: [PlutoState.THINKING, PlutoState.SPEAKING, PlutoState.LISTENING, PlutoState.ERROR],
        PlutoState.SPEAKING: [PlutoState.SUCCESS, PlutoState.LISTENING, PlutoState.IDLE, PlutoState.ERROR],
        PlutoState.SUCCESS: [PlutoState.LISTENING, PlutoState.IDLE, PlutoState.ERROR],
        PlutoState.ERROR: [PlutoState.LISTENING, PlutoState.IDLE],
    }

    def __init__(self) -> None:
        self.current_state = PlutoState.IDLE
        self.previous_state: Optional[PlutoState] = None
        self.state_history: List[StateTransition] = []
        self.state_entered_at: datetime = datetime.now()
        self.listeners: List[Callable[[StateTransition], Any]] = []
        logger.info("state_machine_initialized", initial_state=self.current_state)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def get_current_state(self) -> PlutoState:
        return self.current_state

    def get_previous_state(self) -> Optional[PlutoState]:
        return self.previous_state

    def can_transition(self, to_state: PlutoState) -> bool:
        if isinstance(to_state, str):
            try:
                to_state = PlutoState(to_state)
            except ValueError:
                return False
        return to_state in self.VALID_TRANSITIONS.get(self.current_state, [])

    def is_busy(self) -> bool:
        """True while a task is mid-flight (not idle/listening/success)."""
        return self.current_state in _BUSY_STATES

    def is_ready_for_command(self) -> bool:
        """True when PLUTO may accept a new command."""
        return self.current_state in (
            PlutoState.IDLE, PlutoState.LISTENING, PlutoState.SUCCESS, PlutoState.ERROR
        )

    def get_state_duration(self) -> float:
        return (datetime.now() - self.state_entered_at).total_seconds()

    def get_recent_history(self, count: int = 10) -> List[StateTransition]:
        return self.state_history[-count:]

    def get_history(self) -> List[StateTransition]:
        """Alias used by legacy tests/scripts."""
        return self.state_history

    def get_state_summary(self) -> dict:
        return {
            "current_state": self.current_state,
            "previous_state": self.previous_state,
            "duration_in_state": self.get_state_duration(),
            "state_entered_at": self.state_entered_at.isoformat(),
            "total_transitions": len(self.state_history),
        }

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------
    def _perform(self, new_state: PlutoState, reason: Optional[str], metadata: Optional[dict]) -> bool:
        old_state = self.current_state
        time_in_state = (datetime.now() - self.state_entered_at).total_seconds()
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(),
            reason=reason,
            metadata=metadata,
        )
        self.previous_state = old_state
        self.current_state = new_state
        self.state_entered_at = datetime.now()
        self.state_history.append(transition)
        logger.info(
            "state_transition",
            from_state=old_state.value,
            to_state=new_state.value,
            reason=reason,
            time_in_previous_state=f"{time_in_state:.2f}s",
        )
        return True

    def transition(
        self,
        new_state: PlutoState,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        force: bool = False,
    ) -> bool:
        """
        Transition to a new state (synchronous).

        Returns True when the transition happened. When the transition would be
        invalid, logs a warning and returns False - callers that *must* leave a
        state (e.g. error recovery) should pass ``force=True`` after emitting an
        ``error`` event, never swallow the result silently.

        Does not await listener callbacks; listeners are invoked synchronously
        and must not block (or use :meth:`transition_to` for async listeners).
        """
        if isinstance(new_state, str):
            try:
                new_state = PlutoState(new_state)
            except ValueError:
                logger.error("unknown_state", state=new_state)
                return False

        if not force and not self.can_transition(new_state):
            logger.warning(
                "invalid_state_transition",
                from_state=self.current_state.value,
                to_state=new_state.value,
                reason=reason,
            )
            return False

        ok = self._perform(new_state, reason, metadata)
        # Best-effort listener notification; failures are logged, not raised.
        transition = self.state_history[-1]
        for listener in list(self.listeners):
            try:
                result = listener(transition)
                if asyncio.iscoroutine(result):
                    # Don't leave a dangling coroutine: close it (async callers
                    # should use transition_to()).
                    result.close()
            except Exception as e:  # noqa: BLE001
                logger.error("listener_notification_error", error=str(e))
        return ok

    async def transition_to(
        self,
        new_state: PlutoState,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        force: bool = False,
    ) -> bool:
        """Async transition; notifies async listeners and awaits them."""
        if isinstance(new_state, str):
            try:
                new_state = PlutoState(new_state)
            except ValueError:
                logger.error("unknown_state", state=new_state)
                return False

        if not force and not self.can_transition(new_state):
            logger.warning(
                "invalid_state_transition",
                from_state=self.current_state.value,
                to_state=new_state.value,
                reason=reason,
            )
            return False

        ok = self._perform(new_state, reason, metadata)
        transition = self.state_history[-1]
        for listener in list(self.listeners):
            try:
                result = listener(transition)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:  # noqa: BLE001
                logger.error("listener_notification_error", error=str(e))
        return ok

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    async def handle_error(self, error: Exception, context: Optional[dict] = None) -> None:
        """Record an error and move to ERROR state (always allowed via force)."""
        await self.transition_to(
            PlutoState.ERROR,
            reason=str(error),
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {},
            },
            force=self.current_state not in (PlutoState.ERROR, PlutoState.LISTENING, PlutoState.IDLE),
        )

    async def recover_from_error(self, return_to_listening: bool = True) -> None:
        """Leave ERROR state. Always safe (uses force when needed)."""
        if self.current_state == PlutoState.ERROR:
            await self.transition_to(
                PlutoState.LISTENING if return_to_listening else PlutoState.IDLE,
                reason="error_recovery",
                force=True,
            )

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------
    def add_listener(self, callback: Callable[[StateTransition], Any]) -> None:
        self.listeners.append(callback)

    def reset(self) -> None:
        """Reset to IDLE (e.g. when a session is cleared)."""
        self.current_state = PlutoState.IDLE
        self.previous_state = None
        self.state_entered_at = datetime.now()
        self.state_history = []
        logger.info("state_machine_reset")


# Convenience singleton for REST introspection (the per-session machines are
# owned by SessionManager; this one simply reflects "no WS session is busy").
state_machine = StateMachine()
