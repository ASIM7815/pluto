"""Safe terminal command execution for PLUTO (confirmation-gated).

Commands are classified by core/security before execution:
  SAFE              -> auto-executed
  CONFIRM_REQUIRED  -> the orchestrator pauses for user confirmation
  BLOCKED           -> never executed
Execution uses asyncio subprocess (never blocks the event loop) with a timeout.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from app.core.security import security_validator
from app.core.logging import get_logger
from app.tools.terminal_base import (
    TerminalTool,
    ToolResult,
    SafetyLevel,
)

logger = get_logger(__name__)


class ExecuteCommandTool(TerminalTool):
    """Execute a terminal command with safety classification and timeout."""

    name = "execute_command"
    description = (
        "Runs a shell command on this Linux machine after a safety check. "
        "Destructive or privileged commands ask for your confirmation first."
    )
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    category = "system"
    timeout = 45

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to execute"},
                "working_directory": {"type": "string", "description": "Optional cwd"},
                "timeout": {"type": "integer", "description": "Seconds before timeout", "default": 30},
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        working_directory: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        if not command or not str(command).strip():
            return ToolResult.fail(self.name, "No command was provided.", error_code="BAD_ARGUMENTS")

        safety = security_validator.classify_command(command)
        if safety == "BLOCKED":
            return ToolResult.fail(
                self.name,
                "That command is blocked by PLUTO's security policy.",
                error_code="COMMAND_BLOCKED",
            )
        # CONFIRM_REQUIRED commands are allowed here: the tool-level gate in
        # the orchestrator already asked the user before executing us.

        cwd = os.path.expanduser(working_directory) if working_directory else None
        if cwd and not os.path.isdir(cwd):
            return ToolResult.fail(
                self.name, f"Working directory not found: {working_directory}",
                error_code="DIR_NOT_FOUND",
            )

        result = await self.run_command(
            command, shell=True,
            timeout=int(timeout or 30), cwd=cwd,
        )
        # Keep raw output available for the LLM and activity feed.
        result.data = result.data or {}
        result.data.update({"command": command, "returncode": result.exit_code,
                            "stdout": result.output or "", "safety": safety})
        if result.success:
            result.message = (
                f"Command finished (exit 0). Output: {(result.output or '')[:400]}"
                if result.output else "Command finished successfully."
            )
        return result


TERMINAL_TOOLS: List[TerminalTool] = [ExecuteCommandTool()]
