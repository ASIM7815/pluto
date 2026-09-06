"""PLUTO State Machine - Manages autonomous agent states and transitions"""
from enum import Enum
from typing import Optional, List, Callable, Any
from datetime import datetime
from app.core.logging import get_logger

logger = get_logger(__name__)


class PlutoState(str, Enum):
    """All possible PLUTO states"""
    IDLE = "idle"                    # Waiting for activation
    LISTENING = "listening"          # Recording voice input
    UNDERSTANDING = "understanding"  # Processing speech to text
    THINKING = "thinking"            # GPT-OSS analyzing intent
    PLANNING = "planning"            # Breaking down into steps
    EXECUTING = "executing"          # Running tool actions
    VERIFYING = "verifying"          # Checking if action succeeded
    SPEAKING = "speaking"            # TTS response
    ERROR = "error"                  # Something went wrong


class StateTransition:
    """Represents a state transition"""
    def __init__(
        self,
        from_state: PlutoState,
        to_state: PlutoState,
        timestamp: datetime,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.timestamp = timestamp
        self.reason = reason
        self.metadata = metadata or {}


class StateMachine:
    """
    PLUTO State Machine
    
    Manages state transitions and ensures valid state flow.
    Tracks state history for debugging and logging.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        PlutoState.IDLE: [PlutoState.LISTENING, PlutoState.ERROR],
        PlutoState.LISTENING: [PlutoState.UNDERSTANDING, PlutoState.IDLE, PlutoState.ERROR],
        PlutoState.UNDERSTANDING: [PlutoState.THINKING, PlutoState.LISTENING, PlutoState.ERROR],
        PlutoState.THINKING: [PlutoState.PLANNING, PlutoState.SPEAKING, PlutoState.ERROR],
        PlutoState.PLANNING: [PlutoState.EXECUTING, PlutoState.SPEAKING, PlutoState.ERROR],
        PlutoState.EXECUTING: [PlutoState.VERIFYING, PlutoState.ERROR],
        PlutoState.VERIFYING: [PlutoState.SPEAKING, PlutoState.EXECUTING, PlutoState.ERROR],
        PlutoState.SPEAKING: [PlutoState.LISTENING, PlutoState.IDLE, PlutoState.ERROR],
        PlutoState.ERROR: [PlutoState.LISTENING, PlutoState.IDLE],
    }
    
    def __init__(self):
        self.current_state = PlutoState.IDLE
        self.previous_state: Optional[PlutoState] = None
        self.state_history: List[StateTransition] = []
        self.state_entered_at: datetime = datetime.now()
        self.listeners: List[Callable] = []
        
        logger.info("state_machine_initialized", initial_state=self.current_state)
    
    def get_current_state(self) -> PlutoState:
        """Get the current state"""
        return self.current_state
    
    def get_previous_state(self) -> Optional[PlutoState]:
        """Get the previous state"""
        return self.previous_state
    
    def can_transition(self, to_state: PlutoState) -> bool:
        """
        Check if transition from current state to target state is valid
        
        Args:
            to_state: Target state
            
        Returns:
            True if transition is valid, False otherwise
        """
        return to_state in self.VALID_TRANSITIONS.get(self.current_state, [])
    
    def transition(
        self,
        new_state: PlutoState,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        force: bool = False
    ) -> bool:
        """
        Synchronous transition to a new state (for backward compatibility)
        
        Args:
            new_state: Target state
            reason: Reason for transition (optional)
            metadata: Additional data (optional)
            force: Force transition even if invalid (use carefully)
            
        Returns:
            True if transition succeeded, False otherwise
        """
        # Check if transition is valid
        if not force and not self.can_transition(new_state):
            logger.warning(
                "invalid_state_transition",
                from_state=self.current_state,
                to_state=new_state,
                reason=reason
            )
            return False
        
        # Store previous state
        old_state = self.current_state
        self.previous_state = old_state
        
        # Calculate time spent in previous state
        time_in_state = (datetime.now() - self.state_entered_at).total_seconds()
        
        # Create transition record
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(),
            reason=reason,
            metadata=metadata
        )
        
        # Update state
        self.current_state = new_state
        self.state_entered_at = datetime.now()
        self.state_history.append(transition)
        
        # Log transition
        logger.info(
            "state_transition",
            from_state=old_state,
            to_state=new_state,
            reason=reason,
            time_in_previous_state=f"{time_in_state:.2f}s"
        )
        
        return True
    
    async def transition_to(
        self,
        new_state: PlutoState,
        reason: Optional[str] = None,
        metadata: Optional[dict] = None,
        force: bool = False
    ) -> bool:
        """
        Transition to a new state
        
        Args:
            new_state: Target state
            reason: Reason for transition (optional)
            metadata: Additional data (optional)
            force: Force transition even if invalid (use carefully)
            
        Returns:
            True if transition succeeded, False otherwise
        """
        # Check if transition is valid
        if not force and not self.can_transition(new_state):
            logger.warning(
                "invalid_state_transition",
                from_state=self.current_state,
                to_state=new_state,
                reason=reason
            )
            return False
        
        # Store previous state
        old_state = self.current_state
        self.previous_state = old_state
        
        # Calculate time spent in previous state
        time_in_state = (datetime.now() - self.state_entered_at).total_seconds()
        
        # Create transition record
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(),
            reason=reason,
            metadata=metadata
        )
        
        # Update state
        self.current_state = new_state
        self.state_entered_at = datetime.now()
        self.state_history.append(transition)
        
        # Log transition
        logger.info(
            "state_transition",
            from_state=old_state,
            to_state=new_state,
            reason=reason,
            time_in_previous_state=f"{time_in_state:.2f}s"
        )
        
        # Notify listeners
        await self._notify_listeners(transition)
        
        return True
    
    async def handle_error(self, error: Exception, context: Optional[dict] = None) -> None:
        """
        Handle an error by transitioning to ERROR state
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
        """
        await self.transition_to(
            PlutoState.ERROR,
            reason=str(error),
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {}
            }
        )
    
    async def recover_from_error(self, return_to_listening: bool = True) -> None:
        """
        Recover from error state
        
        Args:
            return_to_listening: If True, return to LISTENING, else IDLE
        """
        if self.current_state == PlutoState.ERROR:
            target_state = PlutoState.LISTENING if return_to_listening else PlutoState.IDLE
            await self.transition_to(
                target_state,
                reason="error_recovery"
            )
    
    def get_state_duration(self) -> float:
        """Get duration in current state (seconds)"""
        return (datetime.now() - self.state_entered_at).total_seconds()
    
    def get_recent_history(self, count: int = 10) -> List[StateTransition]:
        """Get recent state transitions"""
        return self.state_history[-count:]
    
    def add_listener(self, callback: Callable[[StateTransition], Any]) -> None:
        """
        Add a listener to be notified on state changes
        
        Args:
            callback: Async function to call on state change
        """
        self.listeners.append(callback)
    
    async def _notify_listeners(self, transition: StateTransition) -> None:
        """Notify all listeners of state change"""
        for listener in self.listeners:
            try:
                if callable(listener):
                    await listener(transition)
            except Exception as e:
                logger.error("listener_notification_error", error=str(e))
    
    def reset(self) -> None:
        """Reset state machine to initial state"""
        self.current_state = PlutoState.IDLE
        self.previous_state = None
        self.state_entered_at = datetime.now()
        self.state_history = []
        logger.info("state_machine_reset")
    
    def get_state_summary(self) -> dict:
        """Get summary of current state"""
        return {
            "current_state": self.current_state,
            "previous_state": self.previous_state,
            "duration_in_state": self.get_state_duration(),
            "state_entered_at": self.state_entered_at.isoformat(),
            "total_transitions": len(self.state_history)
        }
    
    def is_busy(self) -> bool:
        """Check if PLUTO is busy (not idle or listening)"""
        return self.current_state not in [PlutoState.IDLE, PlutoState.LISTENING]
    
    def is_ready_for_command(self) -> bool:
        """Check if PLUTO is ready to receive commands"""
        return self.current_state in [PlutoState.IDLE, PlutoState.LISTENING]


# Singleton instance
state_machine = StateMachine()
