"""Application Management Tools - open, close, switch, list applications.

Launches are real subprocesses; success is only reported after the target
process is observed running. GUI operations require a graphical session.
"""
from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.tools.terminal_base import (
    TerminalTool,
    ToolResult,
    SafetyLevel,
    VerificationMixin,
    command_exists,
    has_display,
    human_display_hint,
)

logger = get_logger(__name__)

# Common Linux applications -> (executable, description). The executable is
# resolved against PATH with `which`, so an uninstalled app fails honestly.
APP_MAPPINGS: Dict[str, str] = {
    # Browsers
    "firefox": "firefox",
    "browser": "firefox",
    "chrome": "google-chrome",
    "google chrome": "google-chrome",
    "chromium": "chromium",
    "brave": "brave-browser",
    "edge": "microsoft-edge",
    # Code editors
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "sublime": "subl",
    "sublime text": "subl",
    "vim": "vim",
    "emacs": "emacs",
    # File managers
    "files": "nautilus",
    "file manager": "nautilus",
    "dolphin": "dolphin",
    "thunar": "thunar",
    # Terminals
    "terminal": "gnome-terminal",
    "konsole": "konsole",
    "xterm": "xterm",
    "alacritty": "alacritty",
    "gnome terminal": "gnome-terminal",
    # Communication
    "slack": "slack",
    "discord": "discord",
    "telegram": "telegram-desktop",
    "whatsapp": "whatsapp-for-linux",
    "zoom": "zoom",
    # Productivity
    "libreoffice": "libreoffice",
    "writer": "libreoffice",
    "calc": "libreoffice",
    "gimp": "gimp",
    "inkscape": "inkscape",
    "obs": "obs",
    "calculator": "gnome-calculator",
    "settings": "gnome-control-center",
    "control center": "gnome-control-center",
    # Media
    "vlc": "vlc",
    "spotify": "spotify",
    "audacity": "audacity",
    "youtube": "firefox",
    "yt": "firefox",
}

# Executables that are terminal programs (safe without a graphical session).
_TERMINAL_PROGRAMS = {"vim", "emacs", "htop", "top", "git", "bash", "zsh"}


def resolve_executable(app_name: str) -> str:
    """Map a spoken app name to an executable, falling back to the raw name."""
    key = app_name.lower().strip()
    executable = APP_MAPPINGS.get(key, key)
    # Normalise "vs code" -> code style aliases handled by mapping above.
    return executable.split()[0] if executable else key


class OpenApplicationTool(TerminalTool, VerificationMixin):
    """Open (launch) an application."""

    name = "open_application"
    description = (
        "Opens/launches a desktop application (e.g. firefox, vscode, spotify, "
        "nautilus). Reports success only after the app process is verified running."
    )
    safety_level = SafetyLevel.SAFE
    category = "application"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": "Application name (e.g. 'firefox', 'vscode', 'spotify')",
                },
                "arguments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CLI arguments (e.g. a file/folder to open)",
                },
            },
            "required": ["application"],
        }

    async def execute(self, application: str, arguments: Optional[List[str]] = None, **kwargs) -> ToolResult:
        if not application or not str(application).strip():
            return ToolResult.fail(self.name, "No application name was provided.", error_code="BAD_ARGUMENTS")
        app_name = str(application)
        executable = resolve_executable(app_name)
        resolved = shutil.which(executable)

        if not resolved:
            return ToolResult.fail(
                self.name,
                f"'{app_name}' does not appear to be installed (no '{executable}' on PATH). "
                "I can't open an application that isn't on this system.",
                error_code="APP_NOT_FOUND",
            )

        if executable not in _TERMINAL_PROGRAMS and not has_display():
            return ToolResult.fail(
                self.name,
                f"I can't open {app_name} right now: {human_display_hint()}",
                error_code="NO_DISPLAY",
            )

        base_proc = os.path.basename(resolved)
        if await self.check_process_running(base_proc):
            return ToolResult.ok(
                self.name,
                message=f"{app_name} is already running.",
                data={"already_running": True, "process": base_proc},
                context_updates={"current_app": base_proc},
            )

        cmd = [resolved] + (list(arguments or []))
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            return ToolResult.fail(self.name, f"Executable not found: {executable}", error_code="APP_NOT_FOUND")
        except OSError as e:
            return ToolResult.fail(self.name, f"Failed to launch {app_name}: {e}", error_code="LAUNCH_FAILED")

        await asyncio.sleep(1.0)
        started = await self.verify_process_started(base_proc, timeout=6)

        if not started:
            logger.warning("application_open_failed", app=app_name, executable=executable)
            return ToolResult.fail(
                self.name,
                f"I tried to open {app_name} but the process did not start.",
                error_code="LAUNCH_FAILED",
            )

        logger.info("application_opened", app=app_name, executable=executable)
        return ToolResult.ok(
            self.name,
            message=f"Opened {app_name}.",
            data={"process": base_proc, "executable": executable, "pid": process.pid or None},
            verification_passed=True,
            context_updates={"current_app": base_proc},
        )


class CloseApplicationTool(TerminalTool, VerificationMixin):
    """Close a running application."""

    name = "close_application"
    description = "Closes a running application (graceful, then force-kill if requested)."
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    category = "application"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application": {"type": "string", "description": "Application name to close"},
                "force": {"type": "boolean", "description": "Force kill if graceful close fails", "default": False},
            },
            "required": ["application"],
        }

    async def execute(self, application: str, force: bool = False, **kwargs) -> ToolResult:
        executable = resolve_executable(str(application))
        proc_name = os.path.basename(executable)

        if not await self.check_process_running(proc_name):
            return ToolResult.ok(
                self.name, message=f"{application} is not running.", data={"was_running": False}
            )

        await self.run_command(["pkill", "-x", proc_name], check_exit_code=False)
        await asyncio.sleep(1.5)

        if not await self.check_process_running(proc_name):
            return ToolResult.ok(
                self.name,
                message=f"Closed {application}.",
                data={"was_running": True},
                verification_passed=True,
                context_updates={"current_app": None},
            )

        if force:
            await self.run_command(["pkill", "-9", "-x", proc_name], check_exit_code=False)
            await asyncio.sleep(1.0)
            if not await self.check_process_running(proc_name):
                return ToolResult.ok(
                    self.name,
                    message=f"Force closed {application}.",
                    data={"was_running": True, "forced": True},
                    verification_passed=True,
                    context_updates={"current_app": None},
                )

        return ToolResult.fail(
            self.name,
            f"I could not close {application}; the process is still running.",
            error_code="CLOSE_FAILED",
        )


class SwitchToApplicationTool(TerminalTool, VerificationMixin):
    """Switch focus to an application window."""

    name = "switch_to_application"
    description = "Brings an already-running application's window to the foreground."
    safety_level = SafetyLevel.SAFE
    category = "application"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application": {"type": "string", "description": "Application name to focus"}
            },
            "required": ["application"],
        }

    async def execute(self, application: str, **kwargs) -> ToolResult:
        if not has_display():
            return ToolResult.fail(self.name, human_display_hint(), error_code="NO_DISPLAY")
        proc_name = os.path.basename(resolve_executable(str(application)))
        if not await self.check_process_running(proc_name):
            return ToolResult.fail(
                self.name,
                f"{application} is not running, so I can't switch to it.",
                error_code="APP_NOT_RUNNING",
            )

        if command_exists("wmctrl"):
            result = await self.run_command(
                ["wmctrl", "-a", str(application)], check_exit_code=False
            )
            if result.success:
                return ToolResult.ok(
                    self.name, message=f"Switched to {application}.",
                    verification_passed=True,
                    context_updates={"active_window": str(application), "current_app": proc_name},
                )
        if command_exists("xdotool"):
            result = await self.run_command(
                ["xdotool", "search", "--name", str(application), "windowactivate"],
                check_exit_code=False,
            )
            if result.success:
                return ToolResult.ok(
                    self.name, message=f"Switched to {application}.",
                    verification_passed=True,
                    context_updates={"active_window": str(application), "current_app": proc_name},
                )
        return ToolResult.fail(
            self.name,
            f"Could not focus {application} (needs wmctrl or xdotool, and a matching window).",
            error_code="FOCUS_FAILED",
        )


class ListRunningApplicationsTool(TerminalTool):
    """List running GUI applications."""

    name = "list_running_applications"
    description = "Lists the GUI applications currently running on the desktop."
    safety_level = SafetyLevel.SAFE
    category = "application"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        apps: List[Dict[str, Any]] = []

        if command_exists("wmctrl"):
            result = await self.run_command(["wmctrl", "-l", "-p"], check_exit_code=False)
            if result.output:
                for line in result.output.splitlines():
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        apps.append({
                            "window_id": parts[0], "desktop": parts[1],
                            "pid": parts[2], "title": parts[4],
                        })
        if not apps and command_exists("pgrep"):
            # Headless-ish fallback: report known GUI processes by name.
            known = ["firefox", "google-chrome", "chromium", "code", "nautilus",
                     "gnome-terminal", "spotify", "vlc", "slack", "discord"]
            result = await self.run_command(["pgrep", "-l"] + known, check_exit_code=False)
            if result.output:
                for line in result.output.splitlines():
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        apps.append({"pid": parts[0], "title": parts[1]})

        if not apps:
            return ToolResult.ok(
                self.name,
                message="No GUI applications appear to be running (or no window manager is reachable).",
                data={"applications": [], "count": 0},
            )
        return ToolResult.ok(
            self.name,
            message=f"Found {len(apps)} running application(s).",
            data={"applications": apps, "count": len(apps)},
            context_updates={"running_apps": [a.get("title", "") for a in apps if a.get("title")]},
        )


APPLICATION_TOOLS: List[TerminalTool] = [
    OpenApplicationTool(),
    CloseApplicationTool(),
    SwitchToApplicationTool(),
    ListRunningApplicationsTool(),
]
