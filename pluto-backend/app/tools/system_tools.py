"""System Control Tools - real system metrics, processes, volume, clipboard,
screenshot. Every tool reports an honest ToolResult with verification."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil

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


# ---------------------------------------------------------------------------
# System metrics helpers (used by REST routes AND as a tool)
# ---------------------------------------------------------------------------
async def collect_system_metrics() -> Dict[str, Any]:
    """Collect CPU/RAM/storage metrics (best-effort, always returns dict)."""
    try:
        cpu_percent = int(psutil.cpu_percent(interval=0.1))
    except Exception:  # noqa: BLE001
        cpu_percent = 0
    try:
        memory = psutil.virtual_memory()
        ram = int(memory.percent)
    except Exception:  # noqa: BLE001
        ram = 0
    try:
        disk = psutil.disk_usage(os.path.expanduser("~") or "/")
        storage = int(disk.percent)
    except Exception:  # noqa: BLE001
        storage = 0

    gpu = temp = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for entries in temps.values():
                if entries:
                    temp = int(entries[0].current)
                    break
    except Exception:  # noqa: BLE001
        pass

    net_up = net_down = None
    try:
        net = psutil.net_io_counters()
        net_up = f"{net.bytes_sent / (1024 ** 2):.1f} MB"
        net_down = f"{net.bytes_recv / (1024 ** 2):.1f} MB"
    except Exception:  # noqa: BLE001
        pass

    return {
        "cpu": cpu_percent,
        "ram": ram,
        "storage": storage,
        "gpu": gpu,
        "temp": temp,
        "networkUp": net_up,
        "networkDown": net_down,
    }


async def collect_system_info() -> Dict[str, Any]:
    """Detailed system information."""
    import platform

    try:
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = int((datetime.now() - boot).total_seconds())
        hours, rem = divmod(uptime_seconds, 3600)
        minutes, _ = divmod(rem, 60)
        uptime = f"{hours}h {minutes}m"
    except Exception:  # noqa: BLE001
        uptime = "unknown"

    return {
        "os": f"{platform.system()} {platform.machine()}",
        "distro": platform.platform(),
        "host": platform.node(),
        "uptime": uptime,
        "securityStatus": "Sandboxed & permission-gated",
        "voiceEngine": "ElevenLabs / local / browser TTS",
        "llmEngine": "GPT-OSS 120B (OpenAI-compatible)",
    }


def _running_processes(limit: int = 25) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            rows.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                "memory_percent": round(info["memory_percent"] or 0.0, 1),
                "status": info["status"] or "?",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda r: r["cpu_percent"], reverse=True)
    return rows[:max(1, min(int(limit), 100))]


class GetProcessesTool(TerminalTool):
    """List running processes sorted by CPU."""

    name = "get_processes"
    description = "Lists the top running processes by CPU usage."
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max processes", "default": 10}},
            "required": [],
        }

    async def execute(self, limit: int = 10, **kwargs) -> ToolResult:
        rows = _running_processes(limit or 10)
        summary = ", ".join(f"{r['name']} ({r['cpu_percent']}%)" for r in rows[:6])
        return ToolResult.ok(
            self.name,
            message=f"Retrieved {len(rows)} processes. Top: {summary}",
            data={"processes": rows, "count": len(rows)},
        )


class KillProcessTool(TerminalTool):
    """Kill a process by name (confirmation required)."""

    name = "kill_process"
    description = "Terminates a running process by name. Requires user confirmation."
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "process": {"type": "string", "description": "Process name to kill"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["process"],
        }

    async def execute(self, process: str, force: bool = False, **kwargs) -> ToolResult:
        result = await self.run_command(
            ["pkill", "-9" if force else "-TERM", "-x", process], check_exit_code=False
        )
        await asyncio.sleep(0.8)
        still = await self.run_command(["pgrep", "-x", process], check_exit_code=False)
        if still.success and still.output:
            return ToolResult.fail(
                self.name, f"{process} is still running.", error_code="KILL_FAILED"
            )
        return ToolResult.ok(self.name, message=f"Stopped {process}.", verification_passed=True)


class TakeScreenshotTool(TerminalTool, VerificationMixin):
    """Take a screenshot (full/select/window)."""

    name = "take_screenshot"
    description = (
        "Takes a screenshot of the screen ('full'), a selected area ('select') "
        "or the active window ('window') and saves it to ~/Pictures."
    )
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Custom filename (optional)"},
                "area": {
                    "type": "string", "enum": ["full", "select", "window"], "default": "full",
                },
            },
            "required": [],
        }

    async def execute(self, filename: Optional[str] = None, area: str = "full", **kwargs) -> ToolResult:
        if not command_exists("scrot"):
            return ToolResult.fail(
                self.name,
                "The screenshot tool 'scrot' is not installed. Install it with your package manager.",
                error_code="MISSING_DEPENDENCY",
            )
        if not has_display():
            return ToolResult.fail(self.name, human_display_hint(), error_code="NO_DISPLAY")

        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        name = filename or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        if not name.endswith(".png"):
            name += ".png"
        dest = os.path.join(pictures_dir, name)

        cmd = ["scrot"]
        if area == "select":
            cmd += ["-s", "-f"]
        elif area == "window":
            cmd += ["-u"]
        cmd.append(dest)

        result = await self.run_command(cmd, timeout=20, check_exit_code=False)
        if not result.success or not os.path.isfile(dest):
            return ToolResult.fail(
                self.name, "The screenshot could not be captured.",
                error=result.error, error_code="SCREENSHOT_FAILED",
            )
        return ToolResult.ok(
            self.name,
            message=f"Screenshot saved to {dest}",
            data={"path": dest, "filename": name},
            verification_passed=True,
            context_updates={"last_screenshot": dest},
        )


class SetVolumeTool(TerminalTool):
    """Set system volume."""

    name = "set_volume"
    description = "Sets the system volume (0-100) or mutes/unmutes audio."
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "description": "0-100, or 'mute' / 'unmute'",
                }
            },
            "required": ["level"],
        }

    async def execute(self, level: str, **kwargs) -> ToolResult:
        if not command_exists("pactl"):
            return ToolResult.fail(
                self.name,
                "Volume control needs 'pactl' (pipewire/pulseaudio utils), which is not installed.",
                error_code="MISSING_DEPENDENCY",
            )
        raw = str(level or "").strip().lower()
        if raw in ("mute", "muted"):
            result = await self.run_command("pactl set-sink-mute @DEFAULT_SINK@ 1", shell=True)
            if not result.success:
                return ToolResult.fail(self.name, "Could not mute audio.", error_code="VOLUME_FAILED")
            return ToolResult.ok(self.name, "Audio muted.", context_updates={"volume_muted": True})
        if raw in ("unmute", "unmuted"):
            result = await self.run_command("pactl set-sink-mute @DEFAULT_SINK@ 0", shell=True)
            if not result.success:
                return ToolResult.fail(self.name, "Could not unmute audio.", error_code="VOLUME_FAILED")
            return ToolResult.ok(self.name, "Audio unmuted.", context_updates={"volume_muted": False})

        try:
            value = int(raw.rstrip("%"))
        except ValueError:
            return ToolResult.fail(
                self.name, f"'{level}' is not a valid volume. Use 0-100, mute or unmute.",
                error_code="BAD_ARGUMENTS",
            )
        if not 0 <= value <= 100:
            return ToolResult.fail(self.name, "Volume must be between 0 and 100.", error_code="BAD_ARGUMENTS")

        result = await self.run_command(
            f"pactl set-sink-volume @DEFAULT_SINK@ {value}%", shell=True
        )
        if not result.success:
            return ToolResult.fail(self.name, "Could not change the volume.", error_code="VOLUME_FAILED")
        return ToolResult.ok(
            self.name, f"Volume set to {value}%.",
            context_updates={"volume_level": value, "volume_muted": False},
        )


class GetVolumeTool(TerminalTool):
    """Get current volume."""

    name = "get_volume"
    description = "Reads the current system volume level."
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        if not command_exists("pactl"):
            return ToolResult.fail(self.name, "'pactl' is not installed.", error_code="MISSING_DEPENDENCY")
        result = await self.run_command(
            "pactl get-sink-volume @DEFAULT_SINK@ | grep -Po '\\d+(?=%)' | head -1",
            shell=True, check_exit_code=False,
        )
        if result.output and result.output.strip().isdigit():
            volume = int(result.output.strip())
            return ToolResult.ok(
                self.name, f"Current volume: {volume}%.",
                data={"volume": volume}, output=str(volume),
            )
        return ToolResult.fail(self.name, "Could not determine the current volume.", error_code="VOLUME_READ_FAILED")


class CopyToClipboardTool(TerminalTool):
    """Copy text to clipboard."""

    name = "copy_to_clipboard"
    description = "Copies text to the system clipboard."
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to copy"}},
            "required": ["text"],
        }

    async def execute(self, text: str, **kwargs) -> ToolResult:
        tool = "xclip" if command_exists("xclip") else ("wl-copy" if command_exists("wl-copy") else None)
        if tool is None:
            return ToolResult.fail(
                self.name,
                "Clipboard support needs 'xclip' (X11) or 'wl-copy' (Wayland); neither is installed.",
                error_code="MISSING_DEPENDENCY",
            )
        import shlex
        if tool == "xclip":
            result = await self.run_command(
                f"echo {shlex.quote(str(text))} | xclip -selection clipboard", shell=True
            )
        else:
            result = await self.run_command(
                f"echo {shlex.quote(str(text))} | wl-copy", shell=True
            )
        if not result.success:
            return ToolResult.fail(self.name, "Could not copy to clipboard.", error_code="CLIPBOARD_FAILED")
        return ToolResult.ok(
            self.name, f"Copied {len(str(text))} characters to the clipboard.",
            data={"length": len(str(text))},
        )


class GetClipboardTool(TerminalTool):
    """Read clipboard content."""

    name = "get_clipboard"
    description = "Reads the current text from the system clipboard."
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        if command_exists("xclip"):
            result = await self.run_command("xclip -selection clipboard -o", check_exit_code=False)
        elif command_exists("wl-paste"):
            result = await self.run_command("wl-paste", check_exit_code=False)
        else:
            return ToolResult.fail(
                self.name, "Clipboard support needs 'xclip' or 'wl-paste'.", error_code="MISSING_DEPENDENCY"
            )
        text = (result.output or "").strip()
        if not result.success and not text:
            return ToolResult.fail(self.name, "Clipboard is empty or unreadable.", error_code="CLIPBOARD_READ_FAILED")
        return ToolResult.ok(
            self.name, f"Retrieved {len(text)} characters from the clipboard.",
            data={"text": text, "length": len(text)}, output=text,
        )


SYSTEM_TOOLS: List[TerminalTool] = [
    TakeScreenshotTool(),
    SetVolumeTool(),
    GetVolumeTool(),
    CopyToClipboardTool(),
    GetClipboardTool(),
    GetProcessesTool(),
    KillProcessTool(),
]
