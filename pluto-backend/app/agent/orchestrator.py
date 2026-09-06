"""PLUTO Agent Orchestrator V2 - Enhanced with context awareness and Level 1 capabilities.

Runs: IDLE -> LISTENING -> UNDERSTANDING -> THINKING -> PLANNING -> EXECUTING -> VERIFYING -> SPEAKING -> LISTENING (loop)
After speaking, it emits a `listening` event so the frontend auto-returns to
LISTENING and can keep receiving commands continuously.

Level 1 Features:
- Terminal-first desktop control (15+ tools)
- Context-aware planning (remembers current app, files, actions)
- Continuous listening mode
- Verification after each action
"""
import asyncio
import base64
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.agent.tool_registry import tool_registry
from app.agent.session_manager import Session
from app.agent.state_machine import StateMachine, PlutoState
from app.agent.context_manager import ContextManager, Action
from app.tools.registry import get_registry as get_tool_registry_v2
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.gpt_oss import gpt_oss_client, LLMToolCall, LLMResponse
from app.schemas.chat import (
    ActionPreview,
    Activity,
    AgentStateEvent,
    ExecutionStep,
)
from app.voice.elevenlabs import elevenlabs_client
from app.voice.local_tts import local_tts_client

logger = get_logger(__name__)

# push is an async callable that emits an AgentStateEvent to the frontend.
PushEvent = Callable[[AgentStateEvent], Any]


class AgentOrchestrator:
    """Central orchestrator running the autonomous agent loop with Level 1 capabilities."""

    def __init__(self) -> None:
        self.conversation_history: List[Dict[str, str]] = []
        self.state_machine = StateMachine()
        self.context_manager = ContextManager()
        self.tool_registry_v2 = get_tool_registry_v2()
        
        # No longer need async listener for synchronous transition()
        # The sync transition() doesn't call listeners
        
        logger.info(
            "orchestrator_initialized",
            tools_v2=len(self.tool_registry_v2.get_all_tools()),
            tools_legacy=len(tool_registry.get_tool_definitions())
        )

    system_prompt = """You are PLUTO, a futuristic Level 1 autonomous AI desktop assistant running locally on the user's Linux computer. You are the brain and control system for this machine.

LEVEL 1 CAPABILITIES (Terminal-First Desktop Control):
You have 15+ tools across 4 categories:

**Application Tools:**
- open_application: Launch apps (Firefox, VSCode, Spotify, etc.)
- close_application: Close running apps gracefully or force-kill
- switch_to_application: Focus/activate an application window
- list_running_applications: See all open apps

**File Tools:**
- open_file: Open files with default apps (documents, images, videos)
- open_folder: Open directories in file manager
- find_files: Search for files by name pattern
- create_folder: Create new directories
- move_file: Move or rename files
- copy_file: Copy files to new locations

**System Tools:**
- take_screenshot: Capture screen (full/select/window)
- set_volume: Control audio (0-100, mute, unmute)
- get_volume: Check current volume level
- copy_to_clipboard: Copy text to clipboard
- get_clipboard: Get clipboard content

**Browser Tools (Legacy):**
- open_url: Open URLs in browser
- browser_navigate: Navigate and interact with pages
- browser_click, browser_key, etc.

CONTEXT AWARENESS:
You have access to session context including:
- Current active application
- Browser URL and page title (if browser is open)
- Recent 10 actions you've taken
- Search queries and results
- Recent files accessed

When the user gives a follow-up command like "search Iron Man" after "open YouTube", you understand that they mean search ON YouTube because that's the current context.

CONTINUOUS LISTENING MODE:
- After completing a task, you automatically return to LISTENING mode
- The user can give follow-up commands and you'll understand the context
- If the user says "silence", "stop listening", "be quiet", or "shut up", acknowledge briefly and stop

WORKFLOW:
1. UNDERSTAND the user's intent using context
2. PLAN which tool(s) to use
3. EXECUTE tools one by one
4. VERIFY each action succeeded
5. SPEAK one short, natural response
6. Return to LISTENING for next command

IMPORTANT RULES:
1. Use tools for real OS actions. Never fabricate a result.
2. Break complex requests into clear sequential tool calls. After each tool result, verify and decide next step.
3. Keep spoken replies to one or two short sentences that sound natural and helpful.
4. For destructive operations (delete, move, terminal commands) the system will ask the user for confirmation.
5. Use context to understand follow-up commands (e.g., "search" means search in current app)
6. If you are unsure, ask a brief clarifying question rather than guessing.
7. Always answer in the language the user uses.
8. When the user says "silence" or similar, just say "Going silent" and stop.

Respond naturally and helpfully."""

    # ------------------------------------------------------------------
    # Public entry: run one command for a session (WebSocket path)
    # ------------------------------------------------------------------
    async def process_command(self, session: Session, command: str) -> None:
        """Run the agent loop for a command and stream events to the session."""
        try:
            await self._run_task(command, session.push, session)
        except asyncio.CancelledError:
            logger.info("command_cancelled", session=session.id)
            await session.push(AgentStateEvent(type="agent_state", state="idle", task="Stopped."))
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("orchestrator_error", error=str(e))
            await session.push(AgentStateEvent(type="agent_state", state="error", error=str(e)))
        finally:
            session.running = False

    # ------------------------------------------------------------------
    # Public REST entry (backward compatible, auto-approves confirmations)
    # ------------------------------------------------------------------
    async def execute_command(
        self, command: str, context: Optional[Dict[str, Any]] = None
    ) -> "Any":
        """Async generator of AgentStateEvent for non-streaming REST use."""
        events: List[AgentStateEvent] = []

        async def push(event: AgentStateEvent) -> None:
            events.append(event)

        await self._run_task(command, push, None, context)
        for event in events:
            yield event

    # ------------------------------------------------------------------
    # The core loop
    # ------------------------------------------------------------------
    async def _run_task(
        self,
        command: str,
        push: PushEvent,
        session: Optional[Session],
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Transition: IDLE -> LISTENING -> UNDERSTANDING
        self.state_machine.transition(PlutoState.LISTENING)
        
        # Get context summary for LLM
        context_summary = self.context_manager.get_context_summary()
        
        # Merge legacy tool registry with V2 tools
        tools = tool_registry.get_tool_definitions()
        
        # Add V2 tools (terminal-first) to the tool list
        v2_schemas = self.tool_registry_v2.get_tool_schemas()
        tools.extend(v2_schemas)
        
        history = list(session.history) if session else list(self.conversation_history)
        history.append({"role": "user", "content": command})
        
        # Inject context into system prompt if available
        enhanced_system_prompt = self.system_prompt
        if context_summary:
            enhanced_system_prompt += f"\n\nCURRENT CONTEXT:\n{context_summary}"
        
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": enhanced_system_prompt},
            *history,
        ]

        # Transition: LISTENING -> UNDERSTANDING
        self.state_machine.transition(PlutoState.UNDERSTANDING)
        await push(AgentStateEvent(
            type="agent_state",
            state="understanding",
            task="Parsing natural language request...",
        ))

        final_text: Optional[str] = None
        reasoning_pass = False
        step_counter = 0
        cancelled = False

        for iteration in range(max(1, settings.pluto_max_iterations)):
            if reasoning_pass:
                # Transition: VERIFYING -> THINKING (reasoning about next step)
                self.state_machine.transition(PlutoState.THINKING)
                await push(AgentStateEvent(
                    type="agent_state",
                    state="reasoning",
                    task="Observing result, deciding the next step...",
                ))
            else:
                # Transition: UNDERSTANDING -> THINKING
                self.state_machine.transition(PlutoState.THINKING)
                await push(AgentStateEvent(
                    type="agent_state",
                    state="thinking",
                    task="Analyzing request & selecting the right tool...",
                ))

            response: LLMResponse = await gpt_oss_client.chat(messages, tools)

            if response.tool_calls:
                # Transition: THINKING -> PLANNING
                self.state_machine.transition(PlutoState.PLANNING)
                await push(AgentStateEvent(
                    type="agent_state",
                    state="planning",
                    task=f"Planning {len(response.tool_calls)} action(s)...",
                ))

                # Build execution steps (unique ids) + assistant tool_calls msg
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [],
                }
                step_meta: Dict[str, Dict[str, str]] = {}
                for i, tc in enumerate(response.tool_calls):
                    sid = f"s{step_counter}"
                    step_counter += 1
                    tc_id = tc.id or f"call_{iteration}_{i}"
                    label = self._step_label(tc)
                    step_meta[tc_id] = {"id": sid, "label": label}
                    assistant_msg["tool_calls"].append({
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    })
                    # Emit step once (planning view) as a fresh object.
                    await push(AgentStateEvent(
                        type="execution_step",
                        step=ExecutionStep(id=sid, label=label, status="pending"),
                    ))

                messages.append(assistant_msg)

                # Execute each tool call in this batch
                for i, tc in enumerate(response.tool_calls):
                    tc_id = tc.id or f"call_{iteration}_{i}"
                    sm = step_meta.get(tc_id, {"id": "s0", "label": f"Run {tc.name}"})

                    # Check if tool exists in V2 registry (terminal-first tools)
                    tool_v2 = self.tool_registry_v2.get_tool(tc.name)
                    
                    if tool_v2:
                        # Use V2 tool execution with safety checks
                        permission = tool_v2.safety_level.value
                    else:
                        # Fallback to legacy tool permission
                        permission = tool_registry.get_permission_level(tc.name)
                    
                    if permission == "BLOCKED" or permission == "dangerous":
                        await push(AgentStateEvent(
                            type="agent_state",
                            state="error",
                            error=f"The tool '{tc.name}' is blocked by security policy.",
                        ))
                        cancelled = True
                        break

                    if permission == "CONFIRM_REQUIRED" or permission == "confirm":
                        ok = await self._await_confirmation(push, session, tc)
                        if not ok:
                            await push(AgentStateEvent(
                                type="agent_state",
                                state="error",
                                error=f"Action '{tc.name}' was cancelled by the user.",
                            ))
                            cancelled = True
                            break

                    # Transition: PLANNING -> EXECUTING
                    self.state_machine.transition(PlutoState.EXECUTING)
                    await push(AgentStateEvent(
                        type="agent_state",
                        state="executing",
                        task=f"Executing {tc.name}...",
                        data={"tool": tc.name, "arguments": tc.arguments},
                    ))
                    # Fresh object per emission (status can't corrupt earlier events).
                    await push(AgentStateEvent(
                        type="execution_step",
                        step=ExecutionStep(id=sm["id"], label=sm["label"], status="current"),
                    ))

                    # Execute tool (try V2 first, fallback to legacy)
                    if tool_v2:
                        result = await self.tool_registry_v2.execute_tool(
                            tc.name,
                            tc.arguments,
                            skip_safety_check=True  # Already checked above
                        )
                        # Update context with tool execution
                        action = Action(
                            tool=tc.name,
                            parameters=tc.arguments,
                            result=result.message,
                            success=result.success
                        )
                        self.context_manager.add_action(action)
                        
                        # Update context from tool result
                        if result.context_updates:
                            self.context_manager.update_context(result.context_updates)
                    else:
                        # Legacy tool execution
                        result = await tool_registry.execute_tool(tc.name, **tc.arguments)

                    # Transition: EXECUTING -> VERIFYING
                    self.state_machine.transition(PlutoState.VERIFYING)
                    
                    # Verify result if V2 tool
                    if tool_v2 and result.success:
                        verified = await self.tool_registry_v2.verify_tool_result(
                            tc.name, result, tc.arguments
                        )
                        result.verification_passed = verified
                        logger.info(
                            "tool_verified",
                            tool=tc.name,
                            success=result.success,
                            verified=verified
                        )

                    await push(AgentStateEvent(
                        type="execution_step",
                        step=ExecutionStep(
                            id=sm["id"],
                            label=sm["label"],
                            status="completed" if result.success else "error",
                            detail=result.message or (
                                result.error.get("message") if result.error else None
                            ),
                        ),
                    ))

                    await push(AgentStateEvent(
                        type="activity",
                        activity=self._build_activity(tc, result),
                    ))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc.name,
                        "content": self._summarise_result(result),
                    })

                if cancelled:
                    # Transition back to IDLE on cancellation
                    self.state_machine.transition(PlutoState.IDLE)
                    break

                # Observe the outcome, then Reason on the next pass.
                # State remains in VERIFYING during observation
                await push(AgentStateEvent(
                    type="agent_state",
                    state="observing",
                    task="Checking the result and verifying the outcome...",
                ))
                reasoning_pass = True
                continue

            # No tool call => final natural-language answer.
            final_text = response.content or "Done."
            messages.append({"role": "assistant", "content": final_text})
            break

        if final_text is None:
            final_text = "Task complete. Anything else?"
            messages.append({"role": "assistant", "content": final_text})

        # Persist context (system message excluded) so multi-turn commands keep context.
        new_history = [m for m in messages if m.get("role") != "system"]
        if session:
            session.history = new_history
        else:
            self.conversation_history = new_history

        # If the user rejected/cancelled the action, don't announce a fake
        # success — just return to LISTENING so the loop continues.
        if cancelled:
            self.state_machine.transition(PlutoState.LISTENING)
            if settings.pluto_auto_listen:
                await push(AgentStateEvent(
                    type="agent_state",
                    state="listening",
                    task="Ready for your next command.",
                ))
            return

        # SUCCESS - Transition to SPEAKING
        self.state_machine.transition(PlutoState.SPEAKING)
        await push(AgentStateEvent(
            type="agent_state",
            state="success",
            task=final_text,
            data={"response": final_text},
        ))

        # SPEAK
        if settings.pluto_auto_speak:
            await push(AgentStateEvent(
                type="agent_state",
                state="speaking",
                task="Speaking response...",
            ))
            audio_b64, engine = await self._synthesize_speech(final_text)
            await push(AgentStateEvent(
                type="speak",
                text=final_text,
                audio=audio_b64,
                tts=engine,
            ))

        # AUTO-RETURN TO LISTENING (continuous loop)
        # Transition: SPEAKING -> LISTENING
        self.state_machine.transition(PlutoState.LISTENING)
        if settings.pluto_auto_listen:
            await push(AgentStateEvent(
                type="agent_state",
                state="listening",
                task="Ready for your next command.",
            ))

    # ------------------------------------------------------------------
    # Confirmation gate
    # ------------------------------------------------------------------
    async def _await_confirmation(
        self, push: PushEvent, session: Optional[Session], tc: LLMToolCall
    ) -> bool:
        preview = self._build_preview(tc)
        await push(AgentStateEvent(type="action_preview", preview=preview))
        if session is None:
            # REST fallback auto-approves dangerous actions.
            return True
        session.require_confirmation(tc.name)
        return await session.wait_for_confirmation()

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------
    async def _synthesize_speech(self, text: str) -> Tuple[Optional[str], str]:
        """Synthesize speech using local offline TTS"""
        try:
            audio = await local_tts_client.text_to_speech(text)
            if audio:
                return base64.b64encode(audio).decode("utf-8"), "local_tts"
            return None, "local_tts"
        except Exception as e:
            logger.error("tts_synthesis_error", error=str(e))
            return None, "error"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _step_label(tc: LLMToolCall) -> str:
        # V2 Terminal-first tools
        v2_labels = {
            "open_application": lambda a: f"Launch {a.get('application', 'app')}",
            "close_application": lambda a: f"Close {a.get('application', 'app')}",
            "switch_to_application": lambda a: f"Switch to {a.get('application', 'app')}",
            "list_running_applications": lambda a: "List running apps",
            "open_file": lambda a: f"Open file {a.get('path', '')}",
            "open_folder": lambda a: f"Open folder {a.get('path', '')}",
            "find_files": lambda a: f"Find '{a.get('query', '')}'",
            "create_folder": lambda a: f"Create folder {a.get('path', '')}",
            "move_file": lambda a: f"Move {a.get('source', '')}",
            "copy_file": lambda a: f"Copy {a.get('source', '')}",
            "take_screenshot": lambda a: f"Take screenshot ({a.get('area', 'full')})",
            "set_volume": lambda a: f"Set volume to {a.get('level', '')}",
            "get_volume": lambda a: "Check volume",
            "copy_to_clipboard": lambda a: "Copy to clipboard",
            "get_clipboard": lambda a: "Get clipboard",
        }
        
        # Legacy tools
        labels = {
            "open_url": lambda a: f"Open {a.get('url', '')} in browser",
            "browser_navigate": lambda a: f"Navigate to {a.get('url', '')}",
            "browser_click": lambda a: f"Click {a.get('selector', 'element')}",
            "browser_key": lambda a: f"Press '{a.get('key', '')}'",
            "browser_fullscreen": lambda a: "Enter fullscreen",
            "browser_snapshot": lambda a: "Capture page snapshot",
            "create_directory": lambda a: f"Create directory {a.get('path', '')}",
            "create_file": lambda a: f"Create file {a.get('path', '')}",
            "delete_file": lambda a: f"Delete {a.get('path', '')}",
            "read_file": lambda a: f"Read {a.get('path', '')}",
            "execute_command": lambda a: f"Run: {a.get('command', '')}",
            "get_processes": lambda a: "Fetch running processes",
        }
        
        # Try V2 first, then legacy
        fn = v2_labels.get(tc.name) or labels.get(tc.name)
        return fn(tc.arguments) if fn else f"Run {tc.name}"

    @staticmethod
    def _build_preview(tc: LLMToolCall) -> ActionPreview:
        args = tc.arguments
        if tc.name == "delete_file":
            return ActionPreview(
                type="file_delete",
                title="Confirm File Deletion",
                content=f"PLUTO wants to delete: {args.get('path')}",
                path=args.get("path"),
                requiresConfirmation=True,
            )
        if tc.name == "execute_command":
            return ActionPreview(
                type="command",
                title="Confirm Terminal Command",
                content=f"Execute: {args.get('command')}",
                requiresConfirmation=True,
            )
        return ActionPreview(
            type="automation",
            title=f"Confirm {tc.name}",
            content=json.dumps(args),
            requiresConfirmation=True,
        )

    @staticmethod
    def _build_activity(tc: LLMToolCall, result: Any) -> Activity:
        # V2 tool categories
        v2_category_map = {
            "open_application": "app",
            "close_application": "app",
            "switch_to_application": "app",
            "list_running_applications": "app",
            "open_file": "file",
            "open_folder": "file",
            "find_files": "file",
            "create_folder": "file",
            "move_file": "file",
            "copy_file": "file",
            "take_screenshot": "system",
            "set_volume": "system",
            "get_volume": "system",
            "copy_to_clipboard": "system",
            "get_clipboard": "system",
        }
        
        # Legacy categories
        category_map = {
            "open_url": "app",
            "browser_navigate": "browser",
            "browser_click": "browser",
            "browser_key": "browser",
            "browser_fullscreen": "browser",
            "browser_snapshot": "browser",
            "create_file": "file",
            "create_directory": "file",
            "delete_file": "file",
            "read_file": "file",
            "execute_command": "system",
            "get_processes": "system",
        }
        
        # Merge maps
        all_categories = {**category_map, **v2_category_map}
        
        title = (result.message if result.message else f"Executed {tc.name}").split(".")[0]
        return Activity(
            id=f"act-{int(time.time() * 1000)}",
            title=title,
            description=result.message or "",
            timestamp="Just now",
            status="success" if result.success else "error",
            category=all_categories.get(tc.name, "automation"),
        )

    @staticmethod
    def _summarise_result(result: Any) -> str:
        if result.success:
            data = result.data or {}
            summary = result.message or "Success"
            # Keep key info short so context stays lean.
            if result.tool == "get_processes":
                summary = f"Retrieved {len(data.get('processes', []))} processes."
            elif result.tool in ("create_file", "read_file", "create_directory", "delete_file"):
                summary = f"{result.message} path={data.get('path', '')}"
            elif result.tool == "execute_command":
                summary = f"returncode={data.get('returncode')} stdout={str(data.get('stdout',''))[:400]}"
            return (summary or "OK")[:600]
        return "ERROR: " + (result.error.get("message") if result.error else "unknown error")

    def reset(self) -> None:
        """Reset conversation history."""
        self.conversation_history = []


# Singleton instance
agent_orchestrator = AgentOrchestrator()
