"""Pattern-based orchestrator - NO AI REQUIRED.

Replaces LLM-based orchestration with direct pattern matching for zero-cost operation.
"""
from __future__ import annotations

import asyncio
import base64
import uuid
from typing import Any, Dict, List, Optional

from app.agent.context_manager import context_manager
from app.agent.session_manager import Session
from app.agent.state_machine import PlutoState
from app.agent.pattern_matcher import pattern_matcher
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.chat import (
    ActionPreview,
    Activity,
    AgentStateEvent,
    CommandResponse,
    ExecutionStep,
)
from app.tools.registry import get_registry
from app.tools.terminal_base import SafetyLevel

logger = get_logger(__name__)


class PatternOrchestrator:
    """Pattern-based orchestrator - direct command execution without AI."""

    def __init__(self) -> None:
        self._registry = get_registry()
        logger.info(
            "pattern_orchestrator_initialized",
            tools=len(self._registry.get_all_tools()),
            matcher_commands=len(pattern_matcher.get_capabilities()),
        )

    # ==================================================================
    # Public entry points
    # ==================================================================
    async def process_command(self, session: Session, command: str) -> None:
        """Process command via pattern matching and stream events."""
        try:
            await self._run_task(session, command)
        except asyncio.CancelledError:
            logger.info("command_cancelled", session=session.id)
            await session.push(AgentStateEvent(
                type="agent_state", state="idle", task="Stopped."
            ))
            session.state_machine.transition(
                PlutoState.IDLE, reason="user_interrupt", force=True
            )
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("orchestrator_error", error=str(e))
            await self._fail_task(session, detail=str(e) or "an internal error occurred")
        finally:
            session.running = False

    async def execute_command(
        self,
        command: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> CommandResponse:
        """Non-streaming REST execution with persistent session context."""
        from app.agent.session_manager import session_manager

        sid = (session_id or uuid.uuid4().hex[:12])
        session = session_manager.get_or_create(sid)
        session.confirmation_available = False  # REST: no human to approve

        events: List[AgentStateEvent] = []

        async def collect(event: AgentStateEvent) -> None:
            events.append(event)

        await self._run_task(session, command, push=collect, context=context)

        # Find terminal state
        error_event = next((e for e in events if e.state == "error"), None)
        success_event = next((e for e in events if e.state == "success"), None)
        spoken = next((e for e in reversed(events) if e.type == "speak"), None)
        final = events[-1] if events else None

        if error_event is not None:
            return CommandResponse(
                success=False,
                message=(spoken.text if spoken else error_event.error) or "Command failed",
                state="error",
                session_id=sid,
                data={"response": spoken.text if spoken else error_event.error,
                      "events": [e.model_dump() for e in events]},
            )
        if success_event is not None:
            message = success_event.task or "Done."
            return CommandResponse(
                success=True,
                message=message,
                state="success",
                session_id=sid,
                data={"response": message, "events": [e.model_dump() for e in events]},
            )
        
        return CommandResponse(
            success=True,
            message=(final.task if final and final.task else "Done."),
            state=(final.state or "idle") if final else "idle",
            session_id=sid,
            data={"events": [e.model_dump() for e in events]},
        )

    # ==================================================================
    # The core loop (pattern-based, no AI)
    # ==================================================================
    async def _run_task(
        self,
        session: Session,
        command: str,
        push=None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        session_id = session.id
        sm = session.state_machine
        push = push or session.push

        async def emit(
            state: PlutoState,
            task: Optional[str] = None,
            reason: Optional[str] = None,
            data: Optional[Dict[str, Any]] = None,
            force: bool = False,
        ) -> bool:
            ok = sm.transition(state, reason=reason, force=force)
            if ok:
                await push(AgentStateEvent(
                    type="agent_state", state=state.value, task=task,
                    data=data, session_id=session_id,
                ))
            return ok

        # State machine prep
        if sm.is_busy():
            await push(AgentStateEvent(
                type="agent_state", state="error",
                error="PLUTO is still busy with the previous command. Please wait.",
                session_id=session_id,
            ))
            return

        current = sm.get_current_state()
        if current == PlutoState.IDLE:
            sm.transition(PlutoState.LISTENING, reason="command_start")
        elif current not in (PlutoState.LISTENING,):
            sm.transition(PlutoState.LISTENING, reason="command_start_recovery", force=True)

        context_manager.get_or_create_context(session_id)
        context_manager.begin_task(session_id, command)
        if context:
            context_manager.update_context(session_id, context)

        # ------------------------------------------------------------------
        # PATTERN MATCHING - NO AI
        # ------------------------------------------------------------------
        await emit(PlutoState.UNDERSTANDING, "Understanding your request...")
        
        matched = pattern_matcher.match_command(command)
        
        if not matched:
            # No pattern matched - provide helpful error
            await self._fail_task(
                session,
                detail=(
                    f"I couldn't understand that command, BOSS. Try commands like:\n"
                    f"- 'Take a screenshot'\n"
                    f"- 'Open YouTube'\n"
                    f"- 'Volume up'\n"
                    f"- 'List running apps'"
                ),
                push=push
            )
            context_manager.end_task(session_id, success=False)
            return
        
        tool_name = matched["command"]
        arguments = matched["arguments"]
        confidence = matched["confidence"]
        
        logger.info(
            "pattern_matched",
            command=tool_name,
            confidence=confidence,
            method=matched["method"]
        )
        
        # ------------------------------------------------------------------
        # EXECUTE THE MATCHED COMMAND
        # ------------------------------------------------------------------
        await emit(PlutoState.THINKING, f"Preparing to execute... (confidence: {int(confidence*100)}%)")
        
        tool = self._registry.get_tool(tool_name)
        if tool is None:
            await self._fail_task(
                session,
                detail=f"The command '{tool_name}' is not available right now.",
                push=push
            )
            context_manager.end_task(session_id, success=False)
            return
        
        # Safety check
        if self._requires_confirmation(tool_name, arguments, tool):
            ok = await self._await_confirmation(push, session, tool_name, arguments)
            if not ok:
                context_manager.end_task(session_id, success=False)
                sm.transition(PlutoState.LISTENING, reason="after_cancel", force=True)
                await push(AgentStateEvent(
                    type="agent_state", state="listening",
                    task="Action cancelled. Ready for your next command.", session_id=session_id,
                ))
                return
        
        # Execute
        step_id = "s0"
        label = self._step_label(tool_name, arguments)
        
        await emit(PlutoState.EXECUTING, f"Executing: {label}", reason="tool_execute")
        await push(AgentStateEvent(
            type="execution_step",
            step=ExecutionStep(id=step_id, label=label, status="current"),
            session_id=session_id,
        ))
        
        result = await self._registry.execute_tool(
            tool_name, arguments, skip_safety_check=True
        )
        
        # Verify
        verified: Optional[bool] = result.verification_passed
        if result.success and verified is None:
            verified = await self._registry.verify_tool_result(
                tool_name, result, arguments
            )
            result.verification_passed = verified
            if not verified:
                result.success = False
                result.error = result.error or "Verification failed after execution."
                result.message = f"Executed but could not be verified: {result.message}"
        
        # Record outcome
        context_manager.record_action(
            session_id,
            tool=tool_name,
            parameters=arguments,
            result=result.message,
            success=result.success,
        )
        if result.context_updates:
            context_manager.update_context(session_id, result.context_updates)
        
        sm.transition(PlutoState.VERIFYING, reason="tool_verify")
        await push(AgentStateEvent(
            type="execution_step",
            step=ExecutionStep(
                id=step_id, label=label,
                status="completed" if result.success else "error",
                detail=result.message,
            ),
            session_id=session_id,
        ))
        await push(AgentStateEvent(
            type="activity",
            activity=self._build_activity(tool_name, arguments, result),
            session_id=session_id,
        ))
        
        if not result.success:
            context_manager.end_task(session_id, success=False)
            await self._fail_task(
                session, 
                detail=result.error or result.message or "the action failed",
                push=push
            )
            return
        
        # ------------------------------------------------------------------
        # SUCCESS - Generate natural response
        # ------------------------------------------------------------------
        context_manager.end_task(session_id, success=True)
        
        final_text = self._generate_response(tool_name, arguments, result)
        
        # Speak the response
        await emit(PlutoState.SPEAKING, "Speaking...", reason="final_answer")
        audio_b64, engine = await self._synthesize_speech(final_text)
        await push(AgentStateEvent(
            type="speak", text=final_text, audio=audio_b64, tts=engine,
            session_id=session_id,
        ))
        
        await emit(
            PlutoState.SUCCESS,
            final_text,
            reason="task_success",
            data={"response": final_text},
        )
        
        sm.transition(PlutoState.LISTENING, reason="auto_listen")
        if settings.pluto_auto_listen:
            await push(AgentStateEvent(
                type="agent_state", state="listening",
                task="Ready for your next command.", session_id=session_id,
            ))

    # ==================================================================
    # Response generation (natural language responses)
    # ==================================================================
    def _generate_response(self, tool_name: str, arguments: Dict, result) -> str:
        """Generate natural language response based on command result."""
        
        responses = {
            "take_screenshot": lambda a, r: f"Screenshot captured, BOSS. Saved to {r.message.split(':')[-1].strip() if ':' in r.message else 'your screenshots folder'}.",
            
            "copy_to_clipboard": lambda a, r: "Copied to clipboard, BOSS. Ready to paste anywhere.",
            
            "get_clipboard": lambda a, r: f"Here's what's in your clipboard: {r.message}",
            
            "set_volume": lambda a, r: f"Volume set to {a.get('level', 50)}%, BOSS.",
            
            "get_volume": lambda a, r: f"Current volume is at {r.message}, BOSS.",
            
            "open_url": lambda a, r: f"Opened {a.get('url', 'the page')}, BOSS. The browser is ready.",
            
            "browser_search": lambda a, r: f"Found results for '{a.get('query', '')}', BOSS. Take a look.",
            
            "browser_click": lambda a, r: "Clicked it, BOSS.",
            
            "close_browser": lambda a, r: "Browser closed, BOSS.",
            
            "browser_fullscreen": lambda a, r: "Browser is now fullscreen, BOSS.",
            
            "browser_snapshot": lambda a, r: "Browser screenshot captured, BOSS.",
            
            "open_application": lambda a, r: f"Opened {a.get('application', 'the app')}, BOSS. Ready to work.",
            
            "close_application": lambda a, r: f"Closed {a.get('application', 'the app')}, BOSS.",
            
            "switch_to_application": lambda a, r: f"Switched to {a.get('application', 'the app')}, BOSS.",
            
            "list_running_applications": lambda a, r: f"Here are your running apps: {r.message}",
            
            "create_file": lambda a, r: f"Created file '{a.get('path', '')}', BOSS.",
            
            "create_folder": lambda a, r: f"Created folder '{a.get('path', '')}', BOSS.",
            
            "read_file": lambda a, r: f"Here's the content:\n{r.message[:200]}{'...' if len(r.message) > 200 else ''}",
            
            "list_directory": lambda a, r: f"Files in {a.get('path', 'directory')}: {r.message}",
            
            "delete_file": lambda a, r: f"Deleted {a.get('path', 'the file')}, BOSS.",
            
            "execute_command": lambda a, r: f"Command executed, BOSS. Output: {r.message[:150]}{'...' if len(r.message) > 150 else ''}",
            
            "get_processes": lambda a, r: f"System processes: {r.message[:200]}{'...' if len(r.message) > 200 else ''}",
        }
        
        generator = responses.get(tool_name)
        if generator:
            try:
                return generator(arguments, result)
            except Exception as e:  # noqa: BLE001
                logger.error("response_generation_error", error=str(e))
        
        # Fallback response
        return f"Done, BOSS. {result.message[:100]}"

    # ==================================================================
    # Failure reporting
    # ==================================================================
    async def _fail_task(
        self, session: Session, detail: Optional[str] = None, push=None
    ) -> None:
        """Emit an honest error, speak it, and return to LISTENING."""
        sm = session.state_machine
        push = push or session.push
        
        if detail:
            message = f"I couldn't complete that, BOSS: {detail} I'm still listening - want me to try again?"
        else:
            message = "Something went wrong, BOSS. I'm still here and listening - want me to try again?"
        
        message = message[:400]
        sm.transition(PlutoState.ERROR, reason="task_failed", force=True)
        await push(AgentStateEvent(
            type="agent_state", state="error",
            error=message, task=message,
            data={"response": message}, session_id=session.id,
        ))
        
        if settings.pluto_auto_speak:
            audio_b64, engine = await self._synthesize_speech(message)
            await push(AgentStateEvent(
                type="speak", text=message, audio=audio_b64, tts=engine,
                session_id=session.id,
            ))
        
        sm.transition(PlutoState.LISTENING, reason="error_recovery", force=True)
        if settings.pluto_auto_listen:
            await push(AgentStateEvent(
                type="agent_state", state="listening",
                task="Ready for your next command.", session_id=session.id,
            ))

    # ==================================================================
    # Confirmation gate
    # ==================================================================
    @staticmethod
    def _classify_terminal_command(arguments: Dict[str, Any]) -> str:
        """Safety classification for execute_command requests."""
        from app.core.security import security_validator

        command = str((arguments or {}).get("command", "")).strip()
        if not command:
            return "SAFE"
        try:
            return security_validator.classify_command(command)
        except Exception:  # noqa: BLE001
            return "CONFIRM_REQUIRED"

    @classmethod
    def _requires_confirmation(cls, tool_name: str, arguments: Dict, tool) -> bool:
        """Whether a command needs user approval."""
        if tool.safety_level != SafetyLevel.CONFIRM_REQUIRED:
            return False
        if tool_name == "execute_command":
            return cls._classify_terminal_command(arguments) == "CONFIRM_REQUIRED"
        return True

    async def _await_confirmation(
        self, push, session: Session, tool_name: str, arguments: Dict
    ) -> bool:
        """Request user confirmation for dangerous actions."""
        preview = ActionPreview(
            tool=tool_name,
            parameters=arguments,
            description=f"Execute: {tool_name}",
            safety_level="confirm",
        )
        
        if getattr(session, "confirmation_available", True) is False:
            await push(AgentStateEvent(
                type="action_preview", preview=preview, session_id=session.id
            ))
            return False
        
        session.require_confirmation(tool_name)
        await push(AgentStateEvent(
            type="action_preview", preview=preview, session_id=session.id
        ))
        return await session.wait_for_confirmation()

    # ==================================================================
    # Speech synthesis
    # ==================================================================
    async def _synthesize_speech(self, text: str) -> tuple[Optional[str], str]:
        """Synthesize speech - try ElevenLabs, then local TTS, then browser."""
        from app.voice.elevenlabs import elevenlabs_client
        from app.voice.local_tts import local_tts_client

        if not elevenlabs_client.mock_mode:
            try:
                audio, engine = await elevenlabs_client.synthesize(text)
                if audio:
                    return base64.b64encode(audio).decode("utf-8"), engine
            except Exception as e:  # noqa: BLE001
                logger.error("elevenlabs_synthesis_error", error=str(e))
            return None, "browser"

        if local_tts_client.can_use():
            try:
                audio = await local_tts_client.text_to_speech(text)
                if audio:
                    return base64.b64encode(audio).decode("utf-8"), "local_tts"
            except Exception as e:  # noqa: BLE001
                logger.error("local_tts_error", error=str(e))
            return None, "browser"

        return None, "browser"

    # ==================================================================
    # Helpers
    # ==================================================================
    @staticmethod
    def _step_label(tool_name: str, arguments: Dict) -> str:
        """Generate human-readable step label."""
        labels = {
            "open_application": lambda a: f"Open {a.get('application', 'app')}",
            "close_application": lambda a: f"Close {a.get('application', 'app')}",
            "switch_to_application": lambda a: f"Switch to {a.get('application', 'app')}",
            "open_url": lambda a: f"Open {a.get('url', '')}",
            "browser_search": lambda a: f"Search '{a.get('query', '')}'",
            "take_screenshot": lambda a: "Take screenshot",
            "set_volume": lambda a: f"Set volume to {a.get('level', '')}%",
            "create_file": lambda a: f"Create file {a.get('path', '')}",
            "create_folder": lambda a: f"Create folder {a.get('path', '')}",
        }
        
        generator = labels.get(tool_name, lambda a: tool_name.replace("_", " ").title())
        return generator(arguments)

    @staticmethod
    def _build_activity(tool_name: str, arguments: Dict, result) -> Activity:
        """Build activity log entry."""
        # Map tool categories
        category_map = {
            "open_application": "app",
            "close_application": "app",
            "switch_to_application": "app",
            "open_url": "browser",
            "browser_search": "browser",
            "browser_click": "browser",
            "close_browser": "browser",
            "create_file": "file",
            "delete_file": "file",
            "read_file": "file",
            "take_screenshot": "system",
            "set_volume": "system",
            "get_volume": "system",
            "copy_to_clipboard": "system",
            "get_clipboard": "system",
        }
        
        return Activity(
            id=f"act_{tool_name}",
            timestamp="",
            title=tool_name.replace("_", " ").title(),
            description=result.message[:100] if result.message else "Executed",
            status="success" if result.success else "error",
            category=category_map.get(tool_name, "system"),
        )


# Singleton instance
pattern_orchestrator = PatternOrchestrator()
