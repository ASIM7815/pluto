"""PLUTO Agent Orchestrator - the brain loop.

Runs: Listen -> Understand -> Plan -> Act -> Observe -> Reason -> Speak -> Listen.
After speaking, it emits a `listening` event so the frontend auto-returns to
LISTENING and can keep receiving commands continuously.
"""
import asyncio
import base64
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.agent.tool_registry import tool_registry
from app.agent.session_manager import Session
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

logger = get_logger(__name__)

# push is an async callable that emits an AgentStateEvent to the frontend.
PushEvent = Callable[[AgentStateEvent], Any]


class AgentOrchestrator:
    """Central orchestrator running the autonomous agent loop."""

    def __init__(self) -> None:
        self.conversation_history: List[Dict[str, str]] = []

    system_prompt = """You are PLUTO, a futuristic AI desktop assistant running locally on the user's Linux computer. You are the brain and control system for this machine.

You have a set of tools to control the computer: filesystem operations, application launching, terminal commands, system monitoring, URL opening and browser automation.

When the user asks you to do something on the computer, you MUST use a tool — never merely describe what you would do. Tools actually execute real actions.

You run in a continuous loop. A typical multi-step flow looks like:
  "Open YouTube" -> tool(open_url) -> observe OK
  -> tool(browser_click) -> observe OK
  ... continue step by step until the task is complete ...
  -> then reply with one short, friendly spoken sentence telling the user what you did.

IMPORTANT RULES:
1. Use tools for real OS actions. Never fabricate a result.
2. Break complex requests into clear sequential tool calls. After each tool result, re-check the situation and call the next tool.
3. Keep spoken replies to one or two short sentences that sound natural and helpful.
4. For destructive operations (delete, terminal commands) the system will ask the user for confirmation before execution.
5. If you are unsure, ask a brief clarifying question rather than guessing a dangerous action.
6. Always answer in the language the user uses.

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
        tools = tool_registry.get_tool_definitions()
        history = list(session.history) if session else list(self.conversation_history)
        history.append({"role": "user", "content": command})
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            *history,
        ]

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
                await push(AgentStateEvent(
                    type="agent_state",
                    state="reasoning",
                    task="Observing result, deciding the next step...",
                ))
            else:
                await push(AgentStateEvent(
                    type="agent_state",
                    state="thinking",
                    task="Analyzing request & selecting the right tool...",
                ))

            response: LLMResponse = await gpt_oss_client.chat(messages, tools)

            if response.tool_calls:
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

                    permission = tool_registry.get_permission_level(tc.name)
                    if permission == "BLOCKED":
                        await push(AgentStateEvent(
                            type="agent_state",
                            state="error",
                            error=f"The tool '{tc.name}' is blocked by security policy.",
                        ))
                        cancelled = True
                        break

                    if permission == "CONFIRM_REQUIRED":
                        ok = await self._await_confirmation(push, session, tc)
                        if not ok:
                            await push(AgentStateEvent(
                                type="agent_state",
                                state="error",
                                error=f"Action '{tc.name}' was cancelled by the user.",
                            ))
                            cancelled = True
                            break

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

                    result = await tool_registry.execute_tool(tc.name, **tc.arguments)

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
                    break

                # Observe the outcome, then Reason on the next pass.
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
            if settings.pluto_auto_listen:
                await push(AgentStateEvent(
                    type="agent_state",
                    state="listening",
                    task="Ready for your next command.",
                ))
            return

        # SUCCESS
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
        audio, engine = await elevenlabs_client.synthesize(text)
        if audio:
            return base64.b64encode(audio).decode("utf-8"), engine
        return None, engine

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _step_label(tc: LLMToolCall) -> str:
        labels = {
            "open_url": lambda a: f"Open {a.get('url', '')} in browser",
            "browser_navigate": lambda a: f"Navigate to {a.get('url', '')}",
            "browser_click": lambda a: f"Click {a.get('selector', 'element')}",
            "browser_key": lambda a: f"Press '{a.get('key', '')}'",
            "browser_fullscreen": lambda a: "Enter fullscreen",
            "browser_snapshot": lambda a: "Capture page snapshot",
            "open_application": lambda a: f"Launch {a.get('application', 'app')}",
            "create_directory": lambda a: f"Create directory {a.get('path', '')}",
            "create_file": lambda a: f"Create file {a.get('path', '')}",
            "delete_file": lambda a: f"Delete {a.get('path', '')}",
            "read_file": lambda a: f"Read {a.get('path', '')}",
            "execute_command": lambda a: f"Run: {a.get('command', '')}",
            "get_processes": lambda a: "Fetch running processes",
        }
        fn = labels.get(tc.name)
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
        category_map = {
            "open_application": "app",
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
        title = (result.message if result.message else f"Executed {tc.name}").split(".")[0]
        return Activity(
            id=f"act-{int(time.time() * 1000)}",
            title=title,
            description=result.message or "",
            timestamp="Just now",
            status="success" if result.success else "error",
            category=category_map.get(tc.name, "automation"),
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
