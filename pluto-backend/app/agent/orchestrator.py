"""PLUTO Agent Orchestrator - the autonomous task loop.

Flow per command (all states live on the session's StateMachine and every
agent_state event is pushed to the frontend so the orb always mirrors reality):

    (IDLE -> LISTENING)
    UNDERSTANDING -> THINKING -> PLANNING -> EXECUTING -> VERIFYING
        -> (tool failed -> ERROR -> LISTENING)
        -> OBSERVING -> REASONING -> THINKING ... (multi-step loop)
    -> SPEAKING -> SUCCESS -> LISTENING        (auto-return, ready for the
                                                 next command)

Key invariants:
- Every ContextManager call is scoped by session_id (the same id the
  frontend/voice/WS session uses).
- The planner NEVER announces success when a tool actually failed: a failed
  tool immediately stops the task and produces an honest error response.
- Tools are executed through the unified registry only.
- No blocking calls: everything is async.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.agent.context_manager import context_manager
from app.agent.session_manager import Session
from app.agent.state_machine import PlutoState
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.gpt_oss import gpt_oss_client, LLMToolCall
from app.schemas.chat import (
    ActionPreview,
    Activity,
    AgentStateEvent,
    CommandResponse,
    ExecutionStep,
)
from app.tools.registry import get_registry
from app.tools.terminal_base import ToolResult, SafetyLevel

logger = get_logger(__name__)


class AgentOrchestrator:
    """Central orchestrator running the autonomous agent loop."""

    system_prompt = """You are PLUTO, a futuristic autonomous AI desktop assistant running locally on the user's Linux computer. You are the brain and control system for this machine.

CAPABILITIES:
You have real tools for desktop control. Use a tool only when it truly needs to run on the machine; answer directly for conversation.

Application tools:
- open_application: launch a desktop app (firefox, vscode, spotify, nautilus, ...)
- close_application / switch_to_application / list_running_applications

File tools:
- create_folder, create_file, read_file, list_directory, find_files, open_file,
  open_folder, move_file, copy_file, delete_file

Browser tools (real Chromium automation):
- open_url: open/navigate to a URL (e.g. "open YouTube" -> https://www.youtube.com)
- browser_search: search a site (site=youtube for "search Iron Man on YouTube")
- browser_click: click an element - give selector (e.g. 'a#video-title') and a
  zero-based index when the user says "the second video" (index 1)
- browser_key, browser_type, browser_fullscreen, browser_snapshot

System tools:
- get_processes, kill_process, take_screenshot, set_volume, get_volume,
  copy_to_clipboard, get_clipboard, execute_command (confirmation-gated)

Messaging tools:
- send_message (uses the configured provider), open_chat_app

CONTEXT AWARENESS:
A CURRENT CONTEXT block is appended below with your active application, browser
URL/title, last search query, and recent actions. USE IT:
- After "Open YouTube", a follow-up "Search Iron Man" means search ON YouTube
  (use browser_search site=youtube), not a fresh unrelated website.
- "Choose the second video" after a search means click the 2nd result
  (browser_click with index 1) on the page you already have open.
- "Create a folder" without a path should use the current directory if known.

CONTINUOUS LISTENING:
After each task you automatically return to LISTENING. The user can immediately
give the next command - treat it as a continuation of the same working session.

HONESTY RULES (never break these):
1. Never claim an action succeeded unless its tool result says success.
2. If a tool reports failure, say so plainly and stop - do not keep planning
   new steps on top of a failed foundation.
3. Destructive operations (delete, move, terminal, close, send) ask for
   confirmation automatically - do not refuse, just let the gate work.
4. Answer in the user's language. If unsure, ask a brief clarifying question.

HOW YOU SPEAK (important - the user wants a communicative assistant, not a
robot that barks one word):
- Be warm, alive and conversational. Address the user as "BOSS" now and then
  (about once per reply) - it is your signature, but do not overuse it.
- After finishing a task, confirm WHAT you did in a natural sentence, add one
  small useful detail (page title, number of results, what you verified), and
  offer or suggest the next step.
- Good: "YouTube is open in Chrome, BOSS - the homepage loaded fine. Want me
  to search for something?"
- Good: "I searched Iron Man on YouTube and the results are on screen - the
  top match is the official trailer. Say 'choose the first one' whenever
  you're ready, BOSS."
- Good (failure): "I couldn't open that, BOSS - the site didn't respond after
  two tries. I'm still listening; want me to retry or open a different site?"
- Never longer than ~4 spoken sentences. No internal jargon, no narration of
  tool names or parameters - keep the magic.

Respond naturally and helpfully."""

    # Optional shorter/longer speaking styles selected via PLUTO_RESPONSE_STYLE.
    _STYLE_OVERRIDES = {
        "concise": (
            "\n\nSTYLE OVERRIDE: keep spoken replies very short - one crisp "
            "sentence confirming the result."
        ),
        "detailed": (
            "\n\nSTYLE OVERRIDE: be extra communicative - up to five sentences, "
            "briefly explaining what you did, what you verified, and suggest "
            "a follow-up action."
        ),
    }

    def __init__(self) -> None:
        self._registry = get_registry()
        logger.info(
            "orchestrator_initialized",
            tools=len(self._registry.get_all_tools()),
            categories=self._registry.get_tool_info()["categories"],
        )

    # ==================================================================
    # Public entry points
    # ==================================================================
    async def process_command(self, session: Session, command: str) -> None:
        """Run the agent loop for a WS session and stream events to it."""
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
        """Non-streaming REST execution with persistent session context.

        Returns a CommandResponse summarising the run. Confirmation-gated
        actions cannot be approved over REST, so they are reported as such.
        """
        from app.agent.session_manager import session_manager

        sid = (session_id or uuid.uuid4().hex[:12])
        session = session_manager.get_or_create(sid)
        session.confirmation_available = False  # REST: no human to approve

        events: List[AgentStateEvent] = []

        async def collect(event: AgentStateEvent) -> None:
            events.append(event)

        await self._run_task(session, command, push=collect, context=context)

        # Reconstruct the same semantics the WS stream shows: prefer the first
        # terminal event in stream order (success/error), and keep the last
        # spoken text as the response message.
        error_event = next((e for e in events if e.state == "error"), None)
        success_event = next((e for e in events if e.state == "success"), None)
        spoken = next((e for e in reversed(events) if e.type == "speak"), None)
        final = events[-1] if events else None

        if error_event is not None:
            return CommandResponse(
                success=False,
                message=(spoken.text if spoken else error_event.error)
                        or "Command failed",
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
        # Cancelled / rejected path already returned to LISTENING.
        return CommandResponse(
            success=True,
            message=(final.task if final and final.task else "Done."),
            state=(final.state or "idle") if final else "idle",
            session_id=sid,
            data={"events": [e.model_dump() for e in events]},
        )

    # ==================================================================
    # The core loop
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

        # A previous REST/WS run may have left the machine mid-task.
        if sm.is_busy():
            await push(AgentStateEvent(
                type="agent_state", state="error",
                error="PLUTO is still busy with the previous command. Please wait.",
                session_id=session_id,
            ))
            return

        # Enter the task from wherever we were (IDLE or LISTENING). Any other
        # state means a previous run left the machine mid-task; recover first.
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
        # Build messages: system prompt + persisted history + new command
        # ------------------------------------------------------------------
        context_summary = context_manager.get_context_summary(session_id)
        enhanced_system_prompt = self.system_prompt
        style = (settings.pluto_response_style or "friendly").strip().lower()
        enhanced_system_prompt += self._STYLE_OVERRIDES.get(style, "")
        if context_summary and context_summary != "No active session context.":
            enhanced_system_prompt += f"\n\nCURRENT CONTEXT:\n{context_summary}"

        history = list(session.history)
        user_content: str = command
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": enhanced_system_prompt},
            *history,
            {"role": "user", "content": user_content},
        ]

        tools = self._registry.get_tool_schemas()

        await emit(PlutoState.UNDERSTANDING, "Parsing your request...")

        final_text: Optional[str] = None
        reasoning_pass = False
        task_failed = False
        cancelled = False
        step_counter = 0
        failure_detail: Optional[str] = None

        try:
            for iteration in range(max(1, settings.pluto_max_iterations)):
                # --- think -------------------------------------------------
                await emit(
                    PlutoState.THINKING,
                    "Reasoning about the next step..."
                    if reasoning_pass else "Analyzing your request...",
                    reason="llm_start",
                )

                response = await gpt_oss_client.chat(messages, tools)

                if response.finish_reason == "error":
                    raise RuntimeError(
                        response.error or "The AI service could not be reached."
                    )

                if not response.tool_calls:
                    final_text = (response.content or "Done.").strip()
                    messages.append({"role": "assistant", "content": final_text})
                    break

                # --- plan --------------------------------------------------
                await emit(
                    PlutoState.PLANNING,
                    f"Planning {len(response.tool_calls)} action(s)...",
                )

                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [],
                }
                for i, tc in enumerate(response.tool_calls):
                    tc_id = tc.id or f"call_{iteration}_{i}"
                    assistant_msg["tool_calls"].append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    })
                messages.append(assistant_msg)

                # --- execute each planned tool ------------------------------
                for i, tc in enumerate(response.tool_calls):
                    tc_id = tc.id or f"call_{iteration}_{i}"
                    step_id = f"s{step_counter}"
                    step_counter += 1
                    label = self._step_label(tc)

                    tool = self._registry.get_tool(tc.name)
                    if tool is None:
                        task_failed = True
                        failure_detail = f"The action '{tc.name}' is not something I can do."
                        await push(AgentStateEvent(
                            type="execution_step",
                            step=ExecutionStep(
                                id=step_id, label=f"Run {tc.name}",
                                status="error", detail=failure_detail,
                            ),
                            session_id=session_id,
                        ))
                        break

                    # Safety gate (unified registry refuses DANGEROUS itself)
                    if tool.safety_level == SafetyLevel.CONFIRM_REQUIRED:
                        ok = await self._await_confirmation(push, session, tc)
                        if not ok:
                            cancelled = True
                            await push(AgentStateEvent(
                                type="agent_state", state="error",
                                error=f"I cancelled the action '{label}' because it needs your approval.",
                                session_id=session_id,
                            ))
                            break

                    await emit(
                        PlutoState.EXECUTING,
                        f"Executing: {label}",
                        reason="tool_execute",
                    )
                    await push(AgentStateEvent(
                        type="execution_step",
                        step=ExecutionStep(id=step_id, label=label, status="current"),
                        session_id=session_id,
                    ))

                    # Real execution (the gate already ran above, so the
                    # registry is told the confirmation is handled).
                    result = await self._registry.execute_tool(
                        tc.name, tc.arguments, skip_safety_check=True
                    )

                    # Verification (an explicit post-check when the tool has one)
                    verified: Optional[bool] = result.verification_passed
                    if result.success and verified is None:
                        verified = await self._registry.verify_tool_result(
                            tc.name, result, tc.arguments
                        )
                        result.verification_passed = verified
                        if not verified:
                            result.success = False
                            result.error = result.error or "Verification failed after execution."
                            result.message = f"Executed but could not be verified: {result.message}"

                    # Record the outcome truthfully.
                    context_manager.record_action(
                        session_id,
                        tool=tc.name,
                        parameters=tc.arguments,
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
                        activity=self._build_activity(tc, result),
                        session_id=session_id,
                    ))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc.name,
                        "content": self._summarise_result(result),
                    })

                    if not result.success:
                        task_failed = True
                        failure_detail = (
                            result.error or result.message or "the action failed"
                        )
                        break
                    if cancelled:
                        break

                if task_failed or cancelled:
                    break

                # --- observe + reason for the next pass ---------------------
                sm.transition(PlutoState.OBSERVING, reason="tool_observe")
                await push(AgentStateEvent(
                    type="agent_state", state="observing",
                    task="Checking the result...", session_id=session_id,
                ))
                sm.transition(PlutoState.REASONING, reason="tool_reason")
                await push(AgentStateEvent(
                    type="agent_state", state="reasoning",
                    task="Verifying and deciding the next step...", session_id=session_id,
                ))
                reasoning_pass = True
                continue

        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("agent_loop_error", session=session_id, error=str(e))
            await self._fail_task(session, f"I hit an error: {e}", push=push)
            context_manager.end_task(session_id, success=False)
            return

        # ------------------------------------------------------------------
        # Persist conversation history (exclude the injected system message).
        # ------------------------------------------------------------------
        session.history = [m for m in messages if m.get("role") != "system"]

        if task_failed:
            context_manager.end_task(session_id, success=False)
            await self._fail_task(session, detail=failure_detail, push=push)
            return

        if cancelled:
            context_manager.end_task(session_id, success=False)
            sm.transition(PlutoState.LISTENING, reason="after_cancel", force=True)
            await push(AgentStateEvent(
                type="agent_state", state="listening",
                task="Ready for your next command.", session_id=session_id,
            ))
            return

        if final_text is None:
            final_text = "Done. Anything else?"

        context_manager.end_task(session_id, success=True)

        # ------------------------------------------------------------------
        # Speak the final answer, then SUCCESS, then auto-return to LISTENING.
        # ------------------------------------------------------------------
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
    # Failure reporting (honest, recoverable)
    # ==================================================================
    async def _fail_task(
        self, session: Session, detail: Optional[str] = None, push=None
    ) -> None:
        """Emit an honest error, speak it, and return to LISTENING.

        ``push`` defaults to ``session.push``; REST mode passes the local
        collector so the events are included in the CommandResponse.
        """
        sm = session.state_machine
        push = push or session.push
        if detail:
            message = f"I couldn't complete that, BOSS: {detail} I'm still listening - want me to try again or do something else?"
        else:
            message = (
                "Something went wrong while carrying out that command, BOSS. "
                "I'm still here and listening - want me to try again?"
            )
        message = message[:400]
        sm.transition(PlutoState.ERROR, reason="task_failed", force=True)
        await push(AgentStateEvent(
            type="agent_state", state="error",
            error=message, task=message,
            data={"response": message}, session_id=session.id,
        ))
        # Say it out loud too, then recover to LISTENING so the loop continues.
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
    async def _await_confirmation(
        self, push, session: Session, tc: LLMToolCall
    ) -> bool:
        preview = self._build_preview(tc)
        if getattr(session, "confirmation_available", True) is False:
            # No human attached (REST fallback): cannot approve.
            await push(AgentStateEvent(
                type="action_preview", preview=preview, session_id=session.id
            ))
            return False
        # Arm the gate BEFORE announcing the preview so an immediate
        # confirm/reject from the client can never be lost to a race.
        session.require_confirmation(tc.name)
        await push(AgentStateEvent(
            type="action_preview", preview=preview, session_id=session.id
        ))
        return await session.wait_for_confirmation()

    # ==================================================================
    # Speech
    # ==================================================================
    async def _synthesize_speech(self, text: str) -> Tuple[Optional[str], str]:
        """Return (base64 audio or None, engine name).

        Order: ElevenLabs (when configured) -> local TTS -> browser TTS.
        """
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
    def _step_label(tc: LLMToolCall) -> str:
        labels = {
            "open_application": lambda a: f"Open {a.get('application', 'app')}",
            "close_application": lambda a: f"Close {a.get('application', 'app')}",
            "switch_to_application": lambda a: f"Switch to {a.get('application', 'app')}",
            "list_running_applications": lambda a: "List running apps",
            "open_url": lambda a: f"Open {a.get('url', '')}",
            "browser_search": lambda a: f"Search '{a.get('query', '')}'",
            "browser_click": lambda a: "Click element",
            "browser_key": lambda a: f"Press {a.get('key', '')}",
            "browser_type": lambda a: "Type text",
            "browser_fullscreen": lambda a: "Fullscreen",
            "browser_snapshot": lambda a: "Read page",
            "send_message": lambda a: f"Send message to {a.get('recipient', '')}",
            "open_chat_app": lambda a: f"Open {a.get('app', '')}",
            "open_file": lambda a: f"Open file {a.get('path', '')}",
            "open_folder": lambda a: f"Open folder {a.get('path', '')}",
            "find_files": lambda a: f"Find '{a.get('query', '')}'",
            "create_folder": lambda a: f"Create folder {a.get('path', '')}",
            "create_file": lambda a: f"Create file {a.get('path', '')}",
            "read_file": lambda a: f"Read {a.get('path', '')}",
            "list_directory": lambda a: f"List {a.get('path', '~')}",
            "delete_file": lambda a: f"Delete {a.get('path', '')}",
            "move_file": lambda a: f"Move {a.get('source', '')}",
            "copy_file": lambda a: f"Copy {a.get('source', '')}",
            "take_screenshot": lambda a: f"Screenshot ({a.get('area', 'full')})",
            "set_volume": lambda a: f"Set volume {a.get('level', '')}",
            "get_volume": lambda a: "Read volume",
            "copy_to_clipboard": lambda a: "Copy to clipboard",
            "get_clipboard": lambda a: "Read clipboard",
            "get_processes": lambda a: "List processes",
            "kill_process": lambda a: f"Stop {a.get('process', '')}",
            "execute_command": lambda a: f"Run command: {a.get('command', '')}",
        }
        fn = labels.get(tc.name)
        try:
            return fn(tc.arguments) if fn else f"Run {tc.name}"
        except Exception:  # noqa: BLE001
            return f"Run {tc.name}"

    @staticmethod
    def _build_preview(tc: LLMToolCall) -> ActionPreview:
        args = tc.arguments
        if tc.name == "delete_file":
            return ActionPreview(
                type="file_delete", title="Confirm File Deletion",
                content=f"PLUTO wants to delete: {args.get('path')}",
                path=args.get("path"), requiresConfirmation=True,
            )
        if tc.name == "execute_command":
            return ActionPreview(
                type="command", title="Confirm Terminal Command",
                content=f"Execute: {args.get('command')}",
                requiresConfirmation=True,
            )
        if tc.name == "send_message":
            return ActionPreview(
                type="message", title="Confirm Message",
                recipient=args.get("recipient"),
                content=args.get("message"),
                requiresConfirmation=True,
            )
        if tc.name in ("close_application", "kill_process", "move_file"):
            return ActionPreview(
                type="automation", title=f"Confirm {tc.name}",
                content=json.dumps(args), requiresConfirmation=True,
            )
        return ActionPreview(
            type="automation", title=f"Confirm {tc.name}",
            content=json.dumps(args), requiresConfirmation=True,
        )

    @staticmethod
    def _build_activity(tc: LLMToolCall, result: ToolResult) -> Activity:
        category_map = {
            "open_application": "app", "close_application": "app",
            "switch_to_application": "app", "list_running_applications": "app",
            "open_url": "browser", "browser_search": "browser",
            "browser_click": "browser", "browser_key": "browser",
            "browser_type": "browser", "browser_fullscreen": "browser",
            "browser_snapshot": "browser",
            "open_file": "file", "open_folder": "file", "find_files": "file",
            "create_folder": "file", "create_file": "file", "read_file": "file",
            "list_directory": "file", "delete_file": "file", "move_file": "file",
            "copy_file": "file",
            "take_screenshot": "system", "set_volume": "system",
            "get_volume": "system", "copy_to_clipboard": "system",
            "get_clipboard": "system", "get_processes": "system",
            "kill_process": "system", "execute_command": "system",
            "send_message": "message", "open_chat_app": "message",
        }
        title = (result.message or f"Executed {tc.name}").split(".")[0]
        return Activity(
            id=f"act-{int(time.time() * 1000)}-{abs(hash(tc.name + str(tc.arguments))) % 100000}",
            title=title,
            description=(result.message or "")[:300],
            timestamp="Just now",
            status="success" if result.success else "error",
            category=category_map.get(tc.name, "automation"),
        )

    @staticmethod
    def _summarise_result(result: ToolResult) -> str:
        """A compact observation fed back to the LLM."""
        if result.success:
            parts = [result.message or "OK"]
            if result.data:
                if "url" in result.data:
                    parts.append(f"url={result.data['url']}")
                if "title" in result.data:
                    parts.append(f"title={result.data['title']}")
                if "count" in result.data:
                    parts.append(f"count={result.data['count']}")
                if "path" in result.data:
                    parts.append(f"path={result.data['path']}")
            return (" | ".join(parts))[:600]
        return f"ERROR ({result.error_code or 'failure'}): {result.error or result.message}"

    def reset(self) -> None:
        """Compatibility hook: clears nothing global (state is per-session)."""
        logger.info("orchestrator_reset_requested")


# Singleton instance
agent_orchestrator = AgentOrchestrator()
