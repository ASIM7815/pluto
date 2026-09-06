"""Context Manager - Maintains session context for autonomous operations"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Action:
    """Represents an action taken by PLUTO"""
    tool: str
    parameters: Dict[str, Any]
    result: Optional[str]
    success: bool
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    """Complete context for a PLUTO session"""
    session_id: str
    
    # Application context
    current_app: Optional[str] = None  # "firefox", "code", etc.
    running_apps: List[str] = field(default_factory=list)
    active_window: Optional[str] = None
    
    # Browser context
    current_browser: Optional[str] = None  # "firefox", "chromium"
    current_url: Optional[str] = None
    current_page_title: Optional[str] = None
    current_page_type: Optional[str] = None  # "youtube_search", "google_results"
    
    # Page elements (for smart interaction)
    visible_elements: List[Dict] = field(default_factory=list)
    interactive_elements: List[Dict] = field(default_factory=list)
    
    # Search context
    last_search_query: Optional[str] = None
    search_results: List[Dict] = field(default_factory=list)
    selected_result_index: Optional[int] = None
    
    # Recent actions (last 10)
    recent_actions: List[Action] = field(default_factory=list)
    
    # Command context
    previous_command: Optional[str] = None
    current_task: Optional[str] = None
    task_steps_completed: int = 0
    
    # File context
    current_directory: Optional[str] = None
    recent_files: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """
    Manages session contexts for autonomous operations
    
    Tracks:
    - Current applications and windows
    - Browser state (URL, page type, elements)
    - Recent actions and their results
    - Search queries and results
    - File operations context
    """
    
    def __init__(self):
        self.contexts: Dict[str, SessionContext] = {}
        self.context_timeout = timedelta(hours=2)  # Auto-clear after 2 hours
        logger.info("context_manager_initialized")
    
    def create_context(self, session_id: str) -> SessionContext:
        """
        Create a new context for a session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            New SessionContext
        """
        context = SessionContext(session_id=session_id)
        self.contexts[session_id] = context
        logger.info("context_created", session=session_id)
        return context
    
    def get_context(self, session_id: str) -> Optional[SessionContext]:
        """
        Get context for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionContext or None if not found
        """
        context = self.contexts.get(session_id)
        
        # Check if context is expired
        if context and self._is_expired(context):
            logger.info("context_expired", session=session_id)
            self.clear_context(session_id)
            return None
        
        return context
    
    def get_or_create_context(self, session_id: str) -> SessionContext:
        """Get existing context or create new one"""
        context = self.get_context(session_id)
        if not context:
            context = self.create_context(session_id)
        return context
    
    def update_context(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> SessionContext:
        """
        Update context fields
        
        Args:
            session_id: Session identifier
            updates: Dictionary of field updates
            
        Returns:
            Updated SessionContext
        """
        context = self.get_or_create_context(session_id)
        
        for key, value in updates.items():
            if hasattr(context, key):
                setattr(context, key, value)
            else:
                context.metadata[key] = value
        
        context.last_activity = datetime.now()
        
        logger.debug("context_updated", session=session_id, updates=list(updates.keys()))
        return context
    
    def add_action(
        self,
        session_id: str,
        tool: str,
        parameters: Dict[str, Any],
        result: Optional[str],
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an action to the context history
        
        Args:
            session_id: Session identifier
            tool: Tool name
            parameters: Tool parameters
            result: Result message
            success: Whether action succeeded
            metadata: Additional metadata
        """
        context = self.get_or_create_context(session_id)
        
        action = Action(
            tool=tool,
            parameters=parameters,
            result=result,
            success=success,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        # Keep only last 10 actions
        context.recent_actions.append(action)
        if len(context.recent_actions) > 10:
            context.recent_actions.pop(0)
        
        context.last_activity = datetime.now()
        
        logger.debug("action_added", session=session_id, tool=tool, success=success)
    
    def update_browser_context(
        self,
        session_id: str,
        url: Optional[str] = None,
        title: Optional[str] = None,
        page_type: Optional[str] = None,
        elements: Optional[List[Dict]] = None
    ) -> None:
        """Update browser-specific context"""
        updates = {}
        
        if url is not None:
            updates["current_url"] = url
        if title is not None:
            updates["current_page_title"] = title
        if page_type is not None:
            updates["current_page_type"] = page_type
        if elements is not None:
            updates["visible_elements"] = elements
        
        self.update_context(session_id, updates)
    
    def update_search_context(
        self,
        session_id: str,
        query: Optional[str] = None,
        results: Optional[List[Dict]] = None,
        selected_index: Optional[int] = None
    ) -> None:
        """Update search-specific context"""
        updates = {}
        
        if query is not None:
            updates["last_search_query"] = query
        if results is not None:
            updates["search_results"] = results
        if selected_index is not None:
            updates["selected_result_index"] = selected_index
        
        self.update_context(session_id, updates)
    
    def get_context_summary(self, session_id: str) -> str:
        """
        Get human-readable context summary for LLM
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context summary as string
        """
        context = self.get_context(session_id)
        if not context:
            return "No active context."
        
        summary_parts = []
        
        # Application context
        if context.current_app:
            summary_parts.append(f"Current app: {context.current_app}")
        if context.active_window:
            summary_parts.append(f"Active window: {context.active_window}")
        
        # Browser context
        if context.current_url:
            summary_parts.append(f"Current URL: {context.current_url}")
        if context.current_page_title:
            summary_parts.append(f"Page title: {context.current_page_title}")
        if context.current_page_type:
            summary_parts.append(f"Page type: {context.current_page_type}")
        
        # Search context
        if context.last_search_query:
            summary_parts.append(f"Last search: '{context.last_search_query}'")
        if context.search_results:
            summary_parts.append(f"Search results: {len(context.search_results)} items")
        
        # Recent actions
        if context.recent_actions:
            recent = context.recent_actions[-3:]  # Last 3 actions
            actions_desc = ", ".join([a.tool for a in recent])
            summary_parts.append(f"Recent actions: {actions_desc}")
        
        # Previous command
        if context.previous_command:
            summary_parts.append(f"Previous command: '{context.previous_command}'")
        
        # Current task
        if context.current_task:
            summary_parts.append(f"Current task: {context.current_task}")
        
        return " | ".join(summary_parts) if summary_parts else "Empty context."
    
    def clear_context(self, session_id: str) -> None:
        """Clear context for a session"""
        if session_id in self.contexts:
            del self.contexts[session_id]
            logger.info("context_cleared", session=session_id)
    
    def clear_search_context(self, session_id: str) -> None:
        """Clear only search-related context"""
        self.update_context(session_id, {
            "last_search_query": None,
            "search_results": [],
            "selected_result_index": None
        })
    
    def cleanup_expired_contexts(self) -> int:
        """
        Remove expired contexts
        
        Returns:
            Number of contexts removed
        """
        expired_sessions = [
            session_id
            for session_id, context in self.contexts.items()
            if self._is_expired(context)
        ]
        
        for session_id in expired_sessions:
            self.clear_context(session_id)
        
        if expired_sessions:
            logger.info("expired_contexts_cleaned", count=len(expired_sessions))
        
        return len(expired_sessions)
    
    def _is_expired(self, context: SessionContext) -> bool:
        """Check if context has expired"""
        return datetime.now() - context.last_activity > self.context_timeout
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all active session IDs"""
        return list(self.contexts.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context manager statistics"""
        return {
            "active_sessions": len(self.contexts),
            "total_actions": sum(
                len(ctx.recent_actions)
                for ctx in self.contexts.values()
            ),
            "sessions_with_browser": sum(
                1 for ctx in self.contexts.values()
                if ctx.current_url
            ),
            "sessions_with_search": sum(
                1 for ctx in self.contexts.values()
                if ctx.last_search_query
            )
        }


# Singleton instance
context_manager = ContextManager()
