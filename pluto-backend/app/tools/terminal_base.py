"""Canonical tool execution foundation for PLUTO.

Every PLUTO tool is a :class:`TerminalTool` (or a plain async callable wrapped
by :class:`FunctionTool`) and returns a :class:`ToolResult`.  One ToolResult
shape is used across the registry, the orchestrator, the REST layer and the
WebSocket activity feed, so nothing downstream has to branch on tool flavour.

Honesty rules enforced here:
- ``success=False`` is returned for any failure (missing binary, timeout,
  non-zero exit, permission, ...); PLUTO never fabricates a success.
- ``verification_passed`` reflects an actual post-check when one exists.
- ``context_updates`` carries state the ContextManager should record.
"""
from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess  # noqa: F401  (used for timeout kill paths)
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from app.core.logging import get_logger

logger = get_logger(__name__)


class SafetyLevel(str, Enum):
    """Tool safety classification."""

    SAFE = "safe"                    # Auto-execute, no confirmation needed
    CONFIRM_REQUIRED = "confirm"     # Ask user before executing
    DANGEROUS = "dangerous"          # Blocked by default, explicit permission required


@dataclass
class ToolResult:
    """Result of a tool execution (single canonical shape)."""

    success: bool
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    verification_passed: Optional[bool] = None
    context_updates: Optional[Dict[str, Any]] = None
    tool: Optional[str] = None
    error_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "data": self.data,
            "verification_passed": self.verification_passed,
            "context_updates": self.context_updates,
            "tool": self.tool,
            "error_code": self.error_code,
        }

    @classmethod
    def ok(
        cls,
        tool: str,
        message: str = "Done.",
        data: Optional[Dict[str, Any]] = None,
        context_updates: Optional[Dict[str, Any]] = None,
        verification_passed: Optional[bool] = None,
        output: Optional[str] = None,
    ) -> "ToolResult":
        return cls(
            success=True, message=message, data=data or {},
            context_updates=context_updates, verification_passed=verification_passed,
            tool=tool, output=output,
        )

    @classmethod
    def fail(
        cls,
        tool: str,
        message: str = "The action failed.",
        error: Optional[str] = None,
        error_code: Optional[str] = None,
        exit_code: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        return cls(
            success=False, message=message, error=error or message,
            error_code=error_code, exit_code=exit_code, data=data or {}, tool=tool,
        )


# Default timeout for subprocess-backed tools.
DEFAULT_TOOL_TIMEOUT = 30


def command_exists(name: str) -> bool:
    """True when ``name`` resolves to an executable on PATH."""
    return shutil.which(name) is not None


def has_display() -> bool:
    """Whether a graphical display is available (X11/Wayland)."""
    return resolve_session_env() is not None


def _list_x11_sockets() -> List[str]:
    """Live X11 sockets under /tmp/.X11-unix (e.g. [':0', ':1'])."""
    found: List[str] = []
    try:
        for name in os.listdir("/tmp/.X11-unix"):
            if name.startswith("X") and name[1:].isdigit():
                found.append(f":{int(name[1:])}")
    except OSError:
        pass
    return sorted(found, key=lambda d: int(d[1:]))


def _list_wayland_sockets() -> List[str]:
    """Live Wayland sockets for this user in XDG_RUNTIME_DIR (wayland-N)."""
    found: List[str] = []
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if runtime and os.path.isdir(runtime):
        try:
            for name in os.listdir(runtime):
                if name.startswith("wayland-") and name[len("wayland-"):].isdigit():
                    found.append(os.path.join(runtime, name))
        except OSError:
            pass
    # Fall back to /run/user/<uid> when XDG_RUNTIME_DIR is not exported.
    if not found:
        try:
            uid_runtime = f"/run/user/{os.getuid()}"
            if os.path.isdir(uid_runtime):
                for name in os.listdir(uid_runtime):
                    if name.startswith("wayland-") and name[len("wayland-"):].isdigit():
                        found.append(os.path.join(uid_runtime, name))
        except OSError:
            pass
    return sorted(found)


def resolve_session_env() -> Optional[Dict[str, str]]:
    """Resolve the environment variables that reach the user's graphical session.

    PLUTO (or its tools) is often started by a service manager, a different
    shell, or a container, so ``DISPLAY``/``WAYLAND_DISPLAY`` may not be
    inherited even though the user has a live desktop. Resolution order:

    1. ``PLUTO_DISPLAY`` - explicit override for X11 (highest priority).
    2. ``DISPLAY`` / ``WAYLAND_DISPLAY`` already in our environment.
    3. Auto-discovery: live X11 sockets in ``/tmp/.X11-unix`` or Wayland
       sockets in the user's runtime dir (same uid).

    Returns a dict of extra environment variables to pass to child processes,
    or ``None`` when no graphical session can be reached.
    """
    env: Dict[str, str] = {}

    override = os.environ.get("PLUTO_DISPLAY", "").strip()
    if override:
        env["DISPLAY"] = override
        xauth = os.path.expanduser("~/.Xauthority")
        if os.path.isfile(xauth):
            env["XAUTHORITY"] = xauth
        return env

    display = os.environ.get("DISPLAY", "").strip()
    wayland = os.environ.get("WAYLAND_DISPLAY", "").strip()
    runtime = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    xdg_runtime_found = bool(runtime) or bool(_list_wayland_sockets())

    if display:
        env["DISPLAY"] = display
    if wayland:
        env["WAYLAND_DISPLAY"] = wayland
    if runtime:
        env["XDG_RUNTIME_DIR"] = runtime
    elif xdg_runtime_found:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"

    if env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"):
        xauth = os.path.expanduser("~/.Xauthority")
        if os.path.isfile(xauth) and "XAUTHORITY" not in env:
            env["XAUTHORITY"] = xauth
        return env

    # Nothing exported -> look for a live session we can attach to.
    x11 = _list_x11_sockets()
    if x11:
        # The highest-numbered display is normally the desktop session
        # (Xvfb / x0vnc / Xwayland often grab lower numbers first).
        env["DISPLAY"] = x11[-1]
        xauth = os.path.expanduser("~/.Xauthority")
        if os.path.isfile(xauth):
            env["XAUTHORITY"] = xauth
        return env

    wayland_sockets = _list_wayland_sockets()
    if wayland_sockets:
        env["WAYLAND_DISPLAY"] = f"wayland-{os.path.basename(wayland_sockets[-1])}"
        env["XDG_RUNTIME_DIR"] = os.path.dirname(wayland_sockets[-1])
        return env

    return None


def human_display_hint() -> str:
    """Explain why GUI operations may fail and how to fix it."""
    return (
        "No graphical display could be reached (DISPLAY/WAYLAND_DISPLAY are "
        "not set and no live X11/Wayland socket was found for this user). "
        "Start PLUTO inside your desktop session, or point it at the display "
        "with PLUTO_DISPLAY (e.g. PLUTO_DISPLAY=:0)."
    )


class TerminalTool:
    """
    Base class for terminal-based tools.

    Subclasses implement ``execute(**kwargs) -> ToolResult`` and may override
    ``verify(result, **kwargs)`` and ``get_parameters_schema()``.
    """

    # Tool metadata (override in subclasses)
    name: str = "base_tool"
    description: str = "Base tool"
    safety_level: SafetyLevel = SafetyLevel.SAFE
    category: str = "system"

    # Command execution settings
    timeout: int = DEFAULT_TOOL_TIMEOUT

    def __init__(self) -> None:
        self.logger = logger

    # ------------------------------------------------------------------
    async def execute(self, **kwargs) -> ToolResult:  # pragma: no cover - interface
        raise NotImplementedError("Subclasses must implement execute()")

    async def verify(self, result: ToolResult, **kwargs) -> bool:
        """Default verification: trust the recorded success."""
        return bool(result.success)

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def get_schema(self) -> Dict[str, Any]:
        """OpenAI function-calling schema (full tool object)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema(),
            },
        }

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------
    async def run_command(
        self,
        command: Union[str, List[str]],
        shell: bool = False,
        timeout: Optional[int] = None,
        check_exit_code: bool = True,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> ToolResult:
        """Execute a command via asyncio subprocess and return a ToolResult.

        Never uses a shell unless the tool explicitly opts in; command strings
        are split with shlex so no injection vector exists through argv.
        """
        timeout = timeout or self.timeout
        try:
            logger.debug(
                "terminal_command_start",
                tool=self.name,
                command=command if isinstance(command, str) else " ".join(command),
                shell=shell,
            )

            if shell:
                if not isinstance(command, str):
                    command = " ".join(command)
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=cwd,
                )
            else:
                argv = shlex.split(command) if isinstance(command, str) else command
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=cwd,
                )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult.fail(
                    self.name,
                    f"The command timed out after {timeout} seconds.",
                    error_code="TIMEOUT", exit_code=-1,
                )

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            success = (process.returncode == 0) if check_exit_code else True

            if success:
                return ToolResult.ok(
                    self.name,
                    message=stdout_text or stderr_text or "Command executed.",
                    output=stdout_text,
                )
            return ToolResult.fail(
                self.name,
                message=stderr_text or stdout_text or f"Command failed (exit {process.returncode}).",
                error=stderr_text or "Command exited non-zero.",
                error_code="COMMAND_ERROR",
                exit_code=process.returncode,
                data={"stdout": stdout_text, "stderr": stderr_text},
            )
        except FileNotFoundError:
            argv0 = argv[0] if "argv" in locals() and isinstance(argv, list) and argv else command
            return ToolResult.fail(
                self.name,
                f"Command not found: {argv0}",
                error_code="COMMAND_NOT_FOUND",
            )
        except Exception as e:  # noqa: BLE001
            logger.error("terminal_command_error", tool=self.name, error=str(e))
            return ToolResult.fail(
                self.name, f"Error executing command: {e}", error_code="EXECUTION_ERROR"
            )

    async def check_command_exists(self, command: str) -> bool:
        return command_exists(command)

    async def check_process_running(self, process_name: str) -> bool:
        result = await self.run_command(["pgrep", "-x", process_name], check_exit_code=False)
        return result.success and bool(result.output)

    async def get_process_pid(self, process_name: str) -> Optional[int]:
        result = await self.run_command(["pgrep", "-x", process_name], check_exit_code=False)
        if result.output:
            try:
                return int(result.output.split("\n")[0])
            except ValueError:
                return None
        return None

    async def file_exists(self, path: str) -> bool:
        return os.path.exists(os.path.expanduser(path))

    async def is_directory(self, path: str) -> bool:
        return os.path.isdir(os.path.expanduser(path))

    async def is_file(self, path: str) -> bool:
        return os.path.isfile(os.path.expanduser(path))


class FunctionTool(TerminalTool):
    """Adapter wrapping a plain async function as a PLUTO tool."""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        parameters_schema: Dict[str, Any],
        safety_level: SafetyLevel = SafetyLevel.SAFE,
        category: str = "system",
        timeout: int = DEFAULT_TOOL_TIMEOUT,
    ) -> None:
        super().__init__()
        self.name = name
        self.description = description
        self.handler = handler
        self._schema = parameters_schema
        self.safety_level = safety_level
        self.category = category
        self.timeout = timeout

    def get_parameters_schema(self) -> Dict[str, Any]:
        return self._schema

    async def execute(self, **kwargs) -> ToolResult:
        result = self.handler(**kwargs)
        if asyncio.iscoroutine(result):
            return await asyncio.wait_for(result, timeout=self.timeout)
        return result


class VerificationMixin:
    """Common verification strategies."""

    async def verify_process_started(self, process_name: str, timeout: int = 6) -> bool:
        for _ in range(timeout):
            if await self.check_process_running(process_name):
                return True
            await asyncio.sleep(1)
        return False

    async def verify_window_exists(self, window_name: str, timeout: int = 5) -> bool:
        import shlex as _shlex
        for _ in range(timeout):
            result = await self.run_command(
                f"wmctrl -l | grep -i {_shlex.quote(window_name)}",
                shell=True, check_exit_code=False,
            )
            if result.success and result.output:
                return True
            await asyncio.sleep(1)
        return False

    async def verify_file_created(self, file_path: str, timeout: int = 5) -> bool:
        for _ in range(timeout):
            if os.path.exists(os.path.expanduser(file_path)):
                return True
            await asyncio.sleep(1)
        return False
