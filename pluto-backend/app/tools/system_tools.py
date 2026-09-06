"""System Control Tools - real system metrics, processes, volume, clipboard,
screenshot. Every tool reports an honest ToolResult with verification."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    resolve_session_env,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Screenshot capture layer
#
# A desktop screenshot needs TWO things: a reachable graphical session and an
# installed capture tool. Different Ubuntu flavours ship different tools:
#   - X11 desktop:  scrot, gnome-screenshot, ImageMagick `import`, spectacle
#   - Wayland:      grim (+ slurp for areas), gnome-screenshot (portal),
#                   spectacle; X11 tools only see XWayland windows.
# PLUTO therefore (1) resolves the real session (env override, inherited env,
# or live /tmp/.X11-unix + /run/user/<uid> sockets), (2) tries every installed
# capture tool in session-appropriate order, and (3) only reports success
# after the produced file is validated as a real, non-trivial image.
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8"
_WEBP_MAGIC = b"RIFF"
# The smallest useful screenshot is far above 1 KB; anything smaller than this
# is almost certainly an error placeholder (0-byte file, X error box, ...).
_MIN_SCREENSHOT_BYTES = 1024


def validate_image_file(path: str, min_bytes: int = _MIN_SCREENSHOT_BYTES) -> Tuple[bool, str]:
    """Confirm ``path`` really contains an image (magic bytes + size).

    Returns ``(ok, kind_or_reason)``. This is the post-capture verification -
    a path alone is never treated as proof that a screenshot exists.
    """
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"cannot stat output file: {e}"
    if size < min_bytes:
        return False, f"output file is only {size} bytes (screenshot looks empty/failed)"
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError as e:
        return False, f"cannot read output file: {e}"
    if head.startswith(_PNG_MAGIC):
        kind = "png"
    elif head.startswith(_JPEG_MAGIC):
        kind = "jpeg"
    elif head.startswith(_WEBP_MAGIC) and head[8:12] == b"WEBP":
        kind = "webp"
    else:
        return False, "file does not start with a PNG/JPEG/WebP signature"
    # Cross-check with ImageMagick when available (validates the whole file).
    if command_exists("identify"):
        try:
            import subprocess

            proc = subprocess.run(
                ["identify", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=15,
            )
            if proc.returncode != 0:
                reason = proc.stderr.decode("utf-8", errors="replace").strip()
                return False, f"ImageMagick rejected the file: {reason[:200]}"
        except Exception as e:  # noqa: BLE001
            logger.warning("screenshot_identify_error", error=str(e))
    return True, kind


async def _run_capture(
    argv: List[str],
    env: Dict[str, str],
    timeout: int = 25,
) -> Tuple[bool, str]:
    """Run one capture command with the session env; returns (ok, detail)."""
    merged = {**os.environ, **env}
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            process.kill()
        except Exception:  # noqa: BLE001
            pass
        return False, f"{os.path.basename(argv[0])} timed out after {timeout}s"
    except FileNotFoundError:
        return False, f"{argv[0]} is not installed"
    except OSError as e:
        return False, f"{os.path.basename(argv[0])}: {e}"

    if process.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        return False, (err or f"{os.path.basename(argv[0])} exited {process.returncode}")
    return True, ""


CaptureFn = Callable[[str, str, Dict[str, str]], Any]


async def _scrot_capture(area: str, dest: str, env: Dict[str, str]) -> Tuple[bool, str]:
    argv = ["scrot"]
    if area == "select":
        argv += ["-s"]
    elif area == "window":
        argv += ["-u"]
    argv += ["-o", dest]
    return await _run_capture(argv, env)


async def _gnome_screenshot_capture(area: str, dest: str, env: Dict[str, str]) -> Tuple[bool, str]:
    argv = ["gnome-screenshot"]
    if area == "select":
        argv += ["-a"]
    elif area == "window":
        argv += ["-w"]
    argv += ["-f", dest]
    return await _run_capture(argv, env)


async def _grim_capture(area: str, dest: str, env: Dict[str, str]) -> Tuple[bool, str]:
    if area == "select":
        if not command_exists("slurp"):
            return False, "grim area capture needs 'slurp', which is not installed"
        ok, geometry = await _run_capture(["slurp", "-f", "%x,%y %wx%h"], env, timeout=20)
        if not ok:
            return False, f"slurp failed: {geometry or 'no area selected'}"
        argv = ["grim", "-g", geometry.strip(), dest]
        return await _run_capture(argv, env, timeout=20)
    if area == "window":
        return False, "grim cannot capture a single window without a wlroots compositor helper"
    return await _run_capture(["grim", dest], env)


async def _spectacle_capture(area: str, dest: str, env: Dict[str, str]) -> Tuple[bool, str]:
    argv = ["spectacle", "-b", "-n"]
    if area == "select":
        argv += ["-r"]
    elif area == "window":
        argv += ["-a"]
    argv += ["-o", dest]
    return await _run_capture(argv, env)


async def _import_capture(area: str, dest: str, env: Dict[str, str]) -> Tuple[bool, str]:
    if area == "select":
        # `import` select mode is interactive (drag to select) - it cannot be
        # driven reliably from an autonomous tool call.
        return False, "ImageMagick select mode is interactive and is not used automatically"
    if area == "window":
        if not command_exists("xdotool"):
            return False, "ImageMagick window capture needs 'xdotool' to find the active window"
        ok, output = await _run_capture(["xdotool", "getactivewindow"], env, timeout=10)
        if not ok or not (output or "").strip():
            return False, "xdotool could not determine the active window"
        window_id = output.strip().splitlines()[-1]
        return await _run_capture(["import", "-window", window_id, dest], env)
    return await _run_capture(["import", "-window", "root", dest], env)


_CAPTURE_BACKENDS: Dict[str, CaptureFn] = {
    "scrot": _scrot_capture,
    "gnome-screenshot": _gnome_screenshot_capture,
    "grim": _grim_capture,
    "spectacle": _spectacle_capture,
    "import": _import_capture,
}

# Session-appropriate tool priority per capture area (X11 first / Wayland first).
_SCREENSHOT_ORDER_X11 = {
    "full": ["scrot", "gnome-screenshot", "spectacle", "import"],
    "window": ["scrot", "gnome-screenshot", "spectacle", "import"],
    "select": ["scrot", "gnome-screenshot", "spectacle"],
}
_SCREENSHOT_ORDER_WAYLAND = {
    "full": ["grim", "gnome-screenshot", "spectacle", "scrot", "import"],
    "window": ["gnome-screenshot", "spectacle", "scrot", "import"],
    "select": ["gnome-screenshot", "spectacle", "scrot"],
}


def _screenshot_order(area: str, env: Dict[str, str]) -> List[str]:
    if env.get("WAYLAND_DISPLAY") and not env.get("PLUTO_PREFER_X11_CAPTURE"):
        return _SCREENSHOT_ORDER_WAYLAND.get(area, [])
    return _SCREENSHOT_ORDER_X11.get(area, [])


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
    if limit is None:
        return rows
    return rows[:max(1, min(int(limit), 100))]


class GetProcessesTool(TerminalTool):
    """List running processes sorted by CPU."""

    name = "get_processes"
    description = (
        "Lists running processes by CPU usage. Pass 'name' to check whether "
        "one process (e.g. firefox, spotify) is running."
    )
    safety_level = SafetyLevel.SAFE
    category = "system"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max processes", "default": 10},
                "name": {"type": "string", "description": "Filter to processes whose name contains this"},
            },
            "required": [],
        }

    async def execute(self, limit: int = 10, name: Optional[str] = None, **kwargs) -> ToolResult:
        if name:
            # A name lookup must scan every process, not just the top-N by CPU,
            # otherwise an idle process (e.g. spotify) is wrongly reported as
            # "not running".
            needle = str(name).strip().casefold()
            rows = [
                r for r in _running_processes(None)
                if needle in str(r.get("name", "")).casefold()
            ]
            if not rows:
                return ToolResult.ok(
                    self.name,
                    message=f"No running process matches '{name}'.",
                    data={"processes": [], "count": 0, "query": name},
                )
            summary = ", ".join(
                f"{r['name']} (PID {r['pid']})" for r in rows[:6]
            )
            return ToolResult.ok(
                self.name,
                message=f"{name} is running: {summary}",
                data={"processes": rows, "count": len(rows), "query": name},
            )
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
        if not process or not str(process).strip():
            return ToolResult.fail(self.name, "No process name was provided.", error_code="BAD_ARGUMENTS")
        process = str(process).strip()

        # Honesty first: only report "stopped" when a matching process existed.
        running = await self.run_command(["pgrep", "-x", process], check_exit_code=False)
        if not running.success or not (running.output or "").strip():
            return ToolResult.ok(
                self.name,
                message=f"{process} is not running, so there was nothing to stop.",
                data={"process": process, "was_running": False},
                verification_passed=True,
            )

        result = await self.run_command(
            ["pkill", "-9" if force else "-TERM", "-x", process], check_exit_code=False
        )
        await asyncio.sleep(0.8)
        still = await self.run_command(["pgrep", "-x", process], check_exit_code=False)
        if still.success and (still.output or "").strip():
            return ToolResult.fail(
                self.name,
                f"{process} is still running and could not be stopped.",
                error_code="KILL_FAILED",
                data={"process": process, "force": force},
            )
        return ToolResult.ok(
            self.name,
            message=f"Stopped {process}.",
            data={"process": process, "was_running": True, "force": force},
            verification_passed=True,
            context_updates={"last_killed_process": process},
        )


class TakeScreenshotTool(TerminalTool, VerificationMixin):
    """Take a screenshot of the real desktop (full screen / window / area)."""

    name = "take_screenshot"
    description = (
        "Takes a screenshot of the desktop: 'full' (whole screen), 'window' "
        "(the active window) or 'select' (interactive area). Saves to ~/Pictures "
        "by default, or to the 'directory' given. The captured image is verified "
        "before success is reported."
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
                "directory": {
                    "type": "string",
                    "description": "Folder to save into (default ~/Pictures). "
                    "Examples: '~/Documents', 'Documents'.",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        filename: Optional[str] = None,
        area: str = "full",
        directory: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        area = (area or "full").strip().lower()
        if area not in ("full", "window", "select"):
            return ToolResult.fail(
                self.name, f"'{area}' is not a valid area (use full, window or select).",
                error_code="BAD_ARGUMENTS",
            )

        # 1) Reach the user's graphical session (the #1 root cause of failed
        #    screenshots: PLUTO started without the desktop's DISPLAY).
        session_env = resolve_session_env()
        if session_env is None:
            return ToolResult.fail(self.name, human_display_hint(), error_code="NO_DISPLAY")

        # 2) Resolve + prepare the destination folder.
        if directory:
            dest_dir = str(directory).strip()
            if not dest_dir.startswith("/") and not dest_dir.startswith("~"):
                dest_dir = os.path.join(os.path.expanduser("~"), dest_dir)
            dest_dir = os.path.expanduser(dest_dir)
        else:
            dest_dir = os.path.expanduser("~/Pictures")
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as e:
            return ToolResult.fail(
                self.name, f"Cannot create the screenshot folder {dest_dir}: {e}",
                error_code="PERMISSION_DENIED",
            )
        if not os.access(dest_dir, os.W_OK):
            return ToolResult.fail(
                self.name, f"The screenshot folder {dest_dir} is not writable.",
                error_code="PERMISSION_DENIED",
            )

        name = (filename or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png").strip()
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            name += ".png"
        dest = os.path.join(dest_dir, name)
        if os.path.exists(dest):
            try:
                os.unlink(dest)
            except OSError:
                pass

        # 3) Try every installed capture tool for this session/area.
        attempts: List[Dict[str, Any]] = []
        tried_backends: List[str] = []
        order = _screenshot_order(area, session_env)
        for tool_name in order:
            backend = _CAPTURE_BACKENDS.get(tool_name)
            if backend is None or not command_exists(tool_name):
                continue
            tried_backends.append(tool_name)
            try:
                ok, detail = await backend(area, dest, session_env)
            except Exception as e:  # noqa: BLE001
                ok, detail = False, f"capture backend crashed: {e}"
            if ok and os.path.isfile(dest):
                valid, kind = validate_image_file(dest)
                if valid:
                    size = os.path.getsize(dest)
                    display_used = (
                        session_env.get("DISPLAY") or session_env.get("WAYLAND_DISPLAY") or "unknown"
                    )
                    return ToolResult.ok(
                        self.name,
                        message=f"Screenshot saved to {dest} ({size:,} bytes, {kind}) "
                        f"using {tool_name}.",
                        data={
                            "path": dest, "filename": os.path.basename(dest),
                            "directory": dest_dir, "area": area, "size": size,
                            "backend": tool_name, "format": kind, "display": display_used,
                        },
                        verification_passed=True,
                        context_updates={"last_screenshot": dest, "recent_files": [dest]},
                    )
                # Backend claimed success but wrote garbage - record and clean up.
                attempts.append({
                    "tool": tool_name, "error": f"produced an invalid image: {kind}",
                })
                try:
                    os.unlink(dest)
                except OSError:
                    pass
            else:
                attempts.append({"tool": tool_name, "error": detail or "capture failed"})

        # 4) Honest failure with the exact reason(s).
        if not tried_backends:
            return ToolResult.fail(
                self.name,
                "No screenshot tool is installed. PLUTO can use scrot, "
                "gnome-screenshot, grim (Wayland), spectacle or ImageMagick "
                "'import' - install one of them (e.g. sudo apt install scrot).",
                error_code="MISSING_DEPENDENCY",
            )
        details = "; ".join(f"{a['tool']}: {a['error']}" for a in attempts)
        return ToolResult.fail(
            self.name,
            f"The screenshot could not be captured (display: "
            f"{session_env.get('DISPLAY') or session_env.get('WAYLAND_DISPLAY')}). {details}",
            error_code="SCREENSHOT_FAILED",
            data={"attempts": attempts, "display": session_env},
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

    async def _set_mute(self, muted: bool) -> ToolResult:
        flag = "1" if muted else "0"
        result = await self.run_command(
            f"pactl set-sink-mute @DEFAULT_SINK@ {flag}", shell=True
        )
        if not result.success:
            return ToolResult.fail(
                self.name, f"Could not {'mute' if muted else 'unmute'} the audio.",
                error=result.error, error_code="VOLUME_FAILED",
            )
        # Verify by reading the sink state back.
        check = await self.run_command(
            "pactl get-sink-mute @DEFAULT_SINK@", shell=True, check_exit_code=False
        )
        state = (check.output or "").strip().lower()
        expected = "yes" if muted else "no"
        verified = expected in state
        if not verified:
            return ToolResult.fail(
                self.name,
                f"Audio was not {'muted' if muted else 'unmuted'} (sink reports '{state or '?'}').",
                error_code="VOLUME_FAILED",
            )
        return ToolResult.ok(
            self.name, f"Audio {'muted' if muted else 'unmuted'}.",
            verification_passed=True,
            context_updates={"volume_muted": muted},
        )

    async def execute(self, level, **kwargs) -> ToolResult:
        if not command_exists("pactl"):
            return ToolResult.fail(
                self.name,
                "Volume control needs 'pactl' (pipewire/pulseaudio utils), which is not installed.",
                error_code="MISSING_DEPENDENCY",
            )
        raw = str(level or "").strip().lower().rstrip("%").strip()
        if raw in ("mute", "muted"):
            return await self._set_mute(muted=True)
        if raw in ("unmute", "unmuted"):
            return await self._set_mute(muted=False)

        try:
            value = int(raw)
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
            return ToolResult.fail(
                self.name, "Could not change the volume.", error=result.error,
                error_code="VOLUME_FAILED",
            )
        # Best-effort read-back; some hardware clamps the requested level.
        check = await self.run_command(
            "pactl get-sink-volume @DEFAULT_SINK@ | grep -Po '\\d+(?=%)' | head -1",
            shell=True, check_exit_code=False,
        )
        readback: Optional[int] = None
        if check.output and check.output.strip().isdigit():
            readback = int(check.output.strip())
            if abs(readback - value) <= 5:
                return ToolResult.ok(
                    self.name, f"Volume set to {value}% (verified).",
                    verification_passed=True,
                    context_updates={"volume_level": value, "volume_muted": False},
                )
        suffix = f" Sink reports {readback}%." if readback is not None else " Could not read the level back."
        return ToolResult.ok(
            self.name, f"Volume change to {value}% was applied.{suffix}",
            data={"requested": value, "reported": readback},
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
        session_env = resolve_session_env()
        if session_env is None:
            return ToolResult.fail(self.name, human_display_hint(), error_code="NO_DISPLAY")
        text = str(text or "")
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
                f"echo {shlex.quote(text)} | xclip -selection clipboard", shell=True
            )
        else:
            result = await self.run_command(
                f"echo {shlex.quote(text)} | wl-copy", shell=True
            )
        if not result.success:
            return ToolResult.fail(
                self.name, f"Could not write to the clipboard: {result.error}",
                error_code="CLIPBOARD_FAILED",
            )

        # Verify by reading the clipboard back - never claim a copy that did
        # not actually land on the user's clipboard.
        reader = "xclip -selection clipboard -o" if tool == "xclip" else "wl-paste"
        check = await self.run_command(reader, shell=True, check_exit_code=False)
        readback = (check.output or "")
        if readback != text:
            return ToolResult.fail(
                self.name,
                "The text was written to the clipboard but could not be verified "
                "(read-back mismatch). The clipboard may be owned by another process.",
                error_code="CLIPBOARD_VERIFY_FAILED",
            )
        return ToolResult.ok(
            self.name, f"Copied {len(text)} characters to the clipboard (verified).",
            data={"length": len(text), "tool": tool},
            verification_passed=True,
            context_updates={"last_clipboard_text": text[:500]},
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
        session_env = resolve_session_env()
        if session_env is None:
            return ToolResult.fail(self.name, human_display_hint(), error_code="NO_DISPLAY")

        # Prefer the reader that matches the active session type.
        if not command_exists("xclip") and not command_exists("wl-paste"):
            return ToolResult.fail(
                self.name, "Clipboard support needs 'xclip' (X11) or 'wl-paste' (Wayland).",
                error_code="MISSING_DEPENDENCY",
            )
        if session_env.get("WAYLAND_DISPLAY") and command_exists("wl-paste"):
            result = await self.run_command("wl-paste", check_exit_code=False)
        elif command_exists("xclip"):
            result = await self.run_command("xclip -selection clipboard -o", check_exit_code=False)
        else:
            result = await self.run_command("wl-paste", check_exit_code=False)

        text = (result.output or "")
        if not result.success and not text:
            return ToolResult.fail(
                self.name,
                f"The clipboard could not be read: {result.error or 'unknown error'}",
                error_code="CLIPBOARD_READ_FAILED",
            )
        if not text:
            return ToolResult.ok(
                self.name, "The clipboard is currently empty.",
                data={"text": "", "length": 0}, output="",
            )
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
