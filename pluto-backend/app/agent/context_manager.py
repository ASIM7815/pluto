"""Context Manager - maintains persistent, session-scoped context.

Every public method takes ``session_id`` so the same context object can serve
any number of concurrent sessions (WebSocket, REST, voice). A session keeps:
- what app/browser/file the user is currently working with,
- the last search + its results (so "choose the second video" resolves),
- the last N tool actions and the previous command (follow-up resolution),
- timestamps for expiry.

The canonical field names below are used by the orchestrator, the routes and
the tool layer, so they must not diverge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum number of actions kept per session (LLM context budget).
MAX_RECENT_ACTIONS = 12


@dataclass
class Action:
    """A single action taken by PLUTO (tool + params + outcome)."""

    tool: str
    parameters: Dict[str, Any]
    result: Optional[str]
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    """Complete persistent context for one PLUTO session."""

    session_id: str

    # Application context
    current_app: Optional[str] = None       # "firefox", "code", ...
    running_apps: List[str] = field(default_factory=list)
    active_window: Optional[str] = None

    # Browser context (canonical names - keep in sync with tools/browser.py)
    current_browser: Optional[str] = None
    current_url: Optional[str] = None
    current_page_title: Optional[str] = None
    current_page_type: Optional[str] = None  # "youtube_home", "youtube_search", ...

    # Page elements (for smart interaction)
    visible_elements: List[Dict] = field(default_factory=list)

    # Search context
    last_search_query: Optional[str] = None
    search_results: List[Dict] = field(default_factory=list)
    selected_result_index: Optional[int] = None

    # Recent actions
    recent_actions: List[Action] = field(default_factory=list)

    # Command/task context (follow-up resolution)
    previous_command: Optional[str] = None
    current_task: Optional[str] = None
    task_steps_completed: int = 0

    # File context
    current_directory: Optional[str] = None
    recent_files: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # Metadata (unknown keys land here)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update(self, updates: Dict[str, Any]) -> None:
        """Apply a flat dict of field updates (unknown keys go to metadata)."""
        for key, value in updates.items():
            if hasattr(self, key) and not key.startswith("_"):
                setattr(self, key, value)
            else:
                self.metadata[key] = value
        self.last_activity = datetime.now()

    def summarize(self) -> str:
        """Human-readable context summary injected into the LLM system prompt."""
        parts: List[str] = []

        if self.current_app:
            parts.append(f"Current app: {self.current_app}")
        if self.active_window:
            parts.append(f"Active window: {self.active_window}")
        if self.current_url:
            parts.append(f"Current URL: {self.current_url}")
        if self.current_page_title:
            parts.append(f"Page title: {self.current_page_title}")
        if self.current_page_type:
            parts.append(f"Page type: {self.current_page_type}")
        if self.last_search_query:
            parts.append(f"Last search: '{self.last_search_query}'")
        if self.search_results:
            parts.append(f"Search results available: {len(self.search_results)} items")
        if self.recent_actions:
            recent = ", ".join(a.tool for a in self.recent_actions[-3:])
            parts.append(f"Recent actions: {recent}")
        if self.previous_command:
            parts.append(f"Previous command: '{self.previous_command}'")
        if self.current_task:
            parts.append(f"Current task: {self.current_task}")
        if self.current_directory:
            parts.append(f"Current directory: {self.current_directory}")
        if self.recent_files:
            parts.append(f"Recent files: {len(self.recent_files)}")

        return " | ".join(parts) if parts else "No prior session context."


class ContextManager:
    """Thread/async-safe registry of per-session contexts."""

    def __init__(self, timeout: Optional[timedelta] = None) -> None:
        self.contexts: Dict[str, SessionContext] = {}
        if timeout is not None:
            self.context_timeout = timeout
        else:
            minutes = max(1, settings.pluto_session_idle_minutes)
            self.context_timeout = timedelta(minutes=minutes)
        logger.info("context_manager_initialized")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def create_context(self, session_id: str) -> SessionContext:
        context = SessionContext(session_id=session_id)
        self.contexts[session_id] = context
        logger.info("context_created", session=session_id)
        return context

    def get_context(self, session_id: str) -> Optional[SessionContext]:
        """Return the session context, or None (also drops expired contexts)."""
        context = self.contexts.get(session_id)
        if context and self._is_expired(context):
            logger.info("context_expired", session=session_id)
            self.clear_context(session_id)
            return None
        return context

    def get_or_create_context(self, session_id: str) -> SessionContext:
        context = self.get_context(session_id)
        if context is None:
            context = self.create_context(session_id)
        return context

    def has_context(self, session_id: str) -> bool:
        return session_id in self.contexts

    def clear_context(self, session_id: str) -> None:
        if session_id in self.contexts:
            del self.contexts[session_id]
            logger.info("context_cleared", session=session_id)

    def reset(self, session_id: str) -> None:
        """Alias for clear_context (kept for API parity)."""
        self.clear_context(session_id)

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------
    def update_context(self, session_id: str, updates: Dict[str, Any]) -> SessionContext:
        """Apply updates (e.g. a tool's ``context_updates``) to a session."""
        context = self.get_or_create_context(session_id)
        context.update(updates or {})
        logger.debug("context_updated", session=session_id, keys=list((updates or {}).keys()))
        return context

    def add_action(
        self,
        session_id: str,
        tool: str,
        parameters: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Action:
        """
        Record one executed tool action against a session.
        (``record_action`` is the orchestrator-facing alias with the same args.)
        """
        context = self.get_or_create_context(session_id)
        action = Action(
            tool=tool,
            parameters=parameters or {},
            result=result,
            success=success,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        context.recent_actions.append(action)
        if len(context.recent_actions) > MAX_RECENT_ACTIONS:
            context.recent_actions = context.recent_actions[-MAX_RECENT_ACTIONS:]
        context.last_activity = datetime.now()
        logger.debug("action_added", session=session_id, tool=tool, success=success)
        return action

    def record_action(
        self,
        session_id: str,
        tool: str,
        parameters: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Action:
        """Orchestrator-facing alias of add_action."""
        return self.add_action(session_id, tool, parameters, result, success, metadata)

    # ------------------------------------------------------------------
    # Domain helpers
    # ------------------------------------------------------------------
    def update_browser_context(
        self,
        session_id: str,
        url: Optional[str] = None,
        title: Optional[str] = None,
        page_type: Optional[str] = None,
        browser: Optional[str] = None,
    ) -> None:
        updates: Dict[str, Any] = {}
        if url is not None:
            updates["current_url"] = url
        if title is not None:
            updates["current_page_title"] = title
        if page_type is not None:
            updates["current_page_type"] = page_type
        if browser is not None:
            updates["current_browser"] = browser
        if updates:
            self.update_context(session_id, updates)

    def update_search_context(
        self,
        session_id: str,
        query: Optional[str] = None,
        results: Optional[List[Dict]] = None,
        selected_index: Optional[int] = None,
    ) -> None:
        updates: Dict[str, Any] = {}
        if query is not None:
            updates["last_search_query"] = query
        if results is not None:
            updates["search_results"] = results
        if selected_index is not None:
            updates["selected_result_index"] = selected_index
        if updates:
            self.update_context(session_id, updates)

    def begin_task(self, session_id: str, command: str) -> None:
        context = self.get_or_create_context(session_id)
        context.previous_command = command
        context.current_task = command
        context.task_steps_completed = 0
        context.last_activity = datetime.now()

    def end_task(self, session_id: str, success: bool = True) -> None:
        context = self.get_or_create_context(session_id)
        context.current_task = None
        context.task_steps_completed = 0
        context.last_activity = datetime.now()

    # ------------------------------------------------------------------
    # Summary / stats / cleanup
    # ------------------------------------------------------------------
    def get_context_summary(self, session_id: str) -> str:
        """Human-readable context summary for the LLM (always a string)."""
        context = self.get_context(session_id)
        return context.summarize() if context else "No active session context."

    def get_context_snapshot(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Serializable dict snapshot for REST consumers."""
        context = self.get_context(session_id)
        if context is None:
            return None
        return {
            "session_id": context.session_id,
            "current_app": context.current_app,
            "active_window": context.active_window,
            "current_url": context.current_url,
            "current_page_title": context.current_page_title,
            "current_directory": context.current_directory,
            "last_search_query": context.last_search_query,
            "search_results_count": len(context.search_results),
            "recent_actions_count": len(context.recent_actions),
            "recent_files": context.recent_files[-10:],
            "previous_command": context.previous_command,
            "last_activity": context.last_activity.isoformat(),
        }

    def cleanup_expired_contexts(self) -> int:
        expired = [
            sid for sid, ctx in self.contexts.items() if self._is_expired(ctx)
        ]
        for sid in expired:
            self.clear_context(sid)
        if expired:
            logger.info("expired_contexts_cleaned", count=len(expired))
        return len(expired)

    def _is_expired(self, context: SessionContext) -> bool:
        return datetime.now() - context.last_activity > self.context_timeout

    def get_all_sessions(self) -> List[str]:
        return list(self.contexts.keys())

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_sessions": len(self.contexts),
            "total_actions": sum(len(c.recent_actions) for c in self.contexts.values()),
            "sessions_with_browser": sum(1 for c in self.contexts.values() if c.current_url),
            "sessions_with_search": sum(1 for c in self.contexts.values() if c.last_search_query),
        }


# Canonical singleton - every component (orchestrator, routes, tools) must use
# this instance so all sessions share one coherent registry keyed by id.
context_manager = ContextManager()
