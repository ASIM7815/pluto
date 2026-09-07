"""Linux platform adapter (reference implementation).

Thin wrapper over the existing OS primitives PLUTO already uses. Kept separate
so Windows/Android can share the same core intelligence while their OS-specific
operations stay here.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import shlex
from typing import Any, Dict, List, Optional, Tuple

from app.platform.base import PlutoPlatform, PlatformResult
from app.core.logging import get_logger

logger = get_logger(__name__)

# Local capture tools, tried in session-appropriate order (X11 vs Wayland).
_ORDER_X11 = {"full": ["scrot", "gnome-screenshot", "spectacle", "import"],
              "window": ["scrot", "gnome-screenshot", "spectacle", "import"],
              "select": ["scrot", "gnome-screenshot", "spectacle"]}
_ORDER_WAYLAND = {"full": ["grim", "gnome-screenshot", "spectacle", "scrot", "import"],
                  "window": ["gnome-screenshot", "spectacle", "scrot", "import"],
                  "select": ["gnome-screenshot", "spectacle", "scrot"]}


def _x11_sockets() -> List[str]:
    try:
        names = os.listdir("/tmp/.X11-unix")
        return [f":{n[1:]}" for n in names if n.startswith("X") and n[1:].isdigit()]
    except OSError:
        return []


def _wayland_sockets() -> List[str]:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if not runtime:
        runtime = f"/run/user/{os.getuid()}"
    try:
        names = os.listdir(runtime)
        return [os.path.join(runtime, n) for n in names
                if n.startswith("wayland-") and n[len("wayland-"):].isdigit()]
    except OSError:
        return []


class LinuxPlatform(PlutoPlatform):
    name = "linux"

    def __init__(self) -> None:
        self._headless_env = None

    def available(self) -> bool:
        return True

    def command_exists(self, command: str) -> bool:
        return shutil.which(command) is not None

    # ------------------------------------------------------------------
    def is_gui_available(self) -> bool:
        if os.environ.get("PLUTO_DISPLAY"):
            return True
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            return True
        return bool(_x11_sockets() or _wayland_sockets())

    def env_for_session(self) -> Optional[Dict[str, str]]:
        override = os.environ.get("PLUTO_DISPLAY", "").strip()
        env: Dict[str, str] = {}
        if override:
            env["DISPLAY"] = override
        elif os.environ.get("DISPLAY"):
            env["DISPLAY"] = os.environ["DISPLAY"]
        elif os.environ.get("WAYLAND_DISPLAY"):
            env["WAYLAND_DISPLAY"] = os.environ["WAYLAND_DISPLAY"]
        else:
            x11 = _x11_sockets()
            if x11:
                env["DISPLAY"] = x11[-1]
            else:
                wl = _wayland_sockets()
                if wl:
                    env["WAYLAND_DISPLAY"] = f"wayland-{os.path.basename(wl[-1])}"
                    env["XDG_RUNTIME_DIR"] = os.path.dirname(wl[-1])
        if not env:
            return None
        xauth = os.path.expanduser("~/.Xauthority")
        if os.path.isfile(xauth) and "XAUTHORITY" not in env:
            env["XAUTHORITY"] = xauth
        return env

    # ------------------------------------------------------------------
    async def open_app(self, application: str, arguments: Optional[List[str]] = None) -> PlatformResult:
        resolved = shutil.which(application)
        if not resolved:
            return PlatformResult.fail(f"'{application}' is not installed on PATH.", "APP_NOT_FOUND")
        if not self.is_gui_available() and application not in ("vim", "emacs", "htop", "top", "git", "bash", "zsh"):
            return PlatformResult.fail("No graphical display is reachable.", "NO_DISPLAY")
        try:
            proc = await asyncio.create_subprocess_exec(
                resolved, *(arguments or []),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            await asyncio.sleep(1)
        except Exception as e:  # noqa: BLE001
            return PlatformResult.fail(f"Launch failed: {e}", "LAUNCH_FAILED")
        if await self.is_process_running(os.path.basename(resolved)):
            return PlatformResult.success({"process": os.path.basename(resolved), "pid": proc.pid})
        return PlatformResult.fail("Process did not start.", "LAUNCH_FAILED")

    async def open_file(self, path: str) -> PlatformResult:
        for opener in ("xdg-open", "gio", "exo-open"):
            if self.command_exists(opener):
                args = ["gio", "open", path] if opener == "gio" else [opener, path]
                return await self.run_command(args, timeout=15)
        return PlatformResult.fail("No default file opener installed.", "MISSING_DEPENDENCY")

    async def open_folder(self, path: str) -> PlatformResult:
        return await self.open_file(path)

    # ------------------------------------------------------------------
    async def is_process_running(self, name: str) -> bool:
        res = await self.run_command(["pgrep", "-x", name], shell=False)
        return res.ok and bool(res.value and str(res.value["stdout"]).strip())

    async def list_processes(self, limit: int = 25) -> PlatformResult:
        res = await self.run_command(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"])
        if not res.ok:
            return res
        rows = []
        for line in str(res.value.get("stdout", "")).splitlines()[1:]:
            parts = line.split(None, 4)
            if len(parts) >= 4:
                rows.append({"pid": parts[0], "name": parts[1],
                             "cpu_percent": parts[2], "memory_percent": parts[3]})
        return PlatformResult.success(rows[:max(1, int(limit))])

    async def kill_process(self, name: str, force: bool = False) -> PlatformResult:
        if not await self.is_process_running(name):
            return PlatformResult.success({"was_running": False})
        sig = "9" if force else "TERM"
        res = await self.run_command(["pkill", f"-{sig}", "-x", name])
        await asyncio.sleep(0.6)
        if await self.is_process_running(name):
            return PlatformResult.fail(f"{name} is still running.", "KILL_FAILED")
        return PlatformResult.success({"was_running": True, "forced": force})

    # ------------------------------------------------------------------
    async def get_volume(self) -> PlatformResult:
        if not self.command_exists("pactl"):
            return PlatformResult.fail("'pactl' is not installed.", "MISSING_DEPENDENCY")
        res = await self.run_command(
            "pactl get-sink-volume @DEFAULT_SINK@ | grep -Po '\\d+(?=%)' | head -1", shell=True)
        if res.ok and res.value.get("stdout", "").strip().isdigit():
            return PlatformResult.success(int(res.value["stdout"].strip()))
        return PlatformResult.fail("Could not read volume.", "VOLUME_READ_FAILED")

    async def set_volume(self, level: str) -> PlatformResult:
        if not self.command_exists("pactl"):
            return PlatformResult.fail("'pactl' is not installed.", "MISSING_DEPENDENCY")
        raw = str(level).strip().lower().rstrip("%")
        if raw in ("mute", "muted"):
            res = await self.run_command("pactl set-sink-mute @DEFAULT_SINK@ 1", shell=True)
        elif raw in ("unmute", "unmuted"):
            res = await self.run_command("pactl set-sink-mute @DEFAULT_SINK@ 0", shell=True)
        else:
            try:
                if not 0 <= int(raw) <= 100:
                    return PlatformResult.fail("Volume must be 0-100.", "BAD_ARGUMENTS")
            except ValueError:
                return PlatformResult.fail(f"'{level}' is not a valid volume.", "BAD_ARGUMENTS")
            res = await self.run_command(f"pactl set-sink-volume @DEFAULT_SINK@ {raw}%", shell=True)
        if not res.ok:
            return PlatformResult.fail("Could not change volume.", "VOLUME_FAILED")
        return PlatformResult.success({"level": raw})

    async def get_clipboard(self) -> PlatformResult:
        if self.command_exists("wl-paste") and os.environ.get("WAYLAND_DISPLAY"):
            res = await self.run_command("wl-paste", shell=True)
        elif self.command_exists("xclip"):
            res = await self.run_command("xclip -selection clipboard -o", shell=True)
        else:
            return PlatformResult.fail("Need xclip or wl-paste.", "MISSING_DEPENDENCY")
        text = (res.value.get("stdout", "") if res.ok else "")
        if not res.ok and not text:
            return PlatformResult.fail(res.error or "clipboard read failed", "CLIPBOARD_READ_FAILED")
        return PlatformResult.success(text)

    async def set_clipboard(self, text: str) -> PlatformResult:
        if self.command_exists("xclip"):
            cmd = f"printf %s {shlex.quote(text)} | xclip -selection clipboard"
        elif self.command_exists("wl-copy"):
            cmd = f"printf %s {shlex.quote(text)} | wl-copy"
        else:
            return PlatformResult.fail("Need xclip or wl-copy.", "MISSING_DEPENDENCY")
        res = await self.run_command(cmd, shell=True)
        return PlatformResult.success({"written": len(text)}) if res.ok else res

    async def take_screenshot(self, area: str, destination: str) -> PlatformResult:
        env = self.env_for_session()
        if env is None:
            return PlatformResult.fail("No graphical display is reachable.", "NO_DISPLAY")
        order = _ORDER_WAYLAND.get(area, _ORDER_X11.get(area, [])) \
            if env.get("WAYLAND_DISPLAY") else _ORDER_X11.get(area, [])
        for tool in order:
            if not self.command_exists(tool):
                continue
            args = self._screenshot_args(tool, area, destination)
            res = await self.run_command(args, env=env, timeout=25)
            if res.ok and os.path.isfile(destination) and os.path.getsize(destination) > 1024:
                return PlatformResult.success({"path": destination, "backend": tool})
        return PlatformResult.fail("Screenshot capture failed.", "SCREENSHOT_FAILED")

    @staticmethod
    def _screenshot_args(tool: str, area: str, dest: str) -> List[str]:
        if tool == "scrot":
            a = ["-s"] if area == "select" else (["-u"] if area == "window" else [])
            return ["scrot", *a, "-o", dest]
        if tool == "gnome-screenshot":
            a = ["-a"] if area == "select" else (["-w"] if area == "window" else [])
            return ["gnome-screenshot", *a, "-f", dest]
        if tool == "grim":
            return ["grim", dest]
        if tool == "spectacle":
            a = ["-r"] if area == "select" else (["-a"] if area == "window" else [])
            return ["spectacle", "-b", "-n", *a, "-o", dest]
        if tool == "import":
            return ["import", "-window", "root", dest]
        return [tool, dest]

    # ------------------------------------------------------------------
    async def run_command(
        self,
        command: Any,
        shell: bool = False,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> PlatformResult:
        timeout = timeout or 30
        merged_env = {**os.environ, **(env or {})}
        try:
            if shell:
                process = await asyncio.create_subprocess_shell(
                    str(command), stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, env=merged_env, cwd=cwd,
                )
            else:
                argv = shlex.split(command) if isinstance(command, str) else list(command)
                process = await asyncio.create_subprocess_exec(
                    *argv, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, env=merged_env, cwd=cwd,
                )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            return PlatformResult.fail("Command timed out.", "TIMEOUT")
        except Exception as e:  # noqa: BLE001
            return PlatformResult.fail(f"Command error: {e}", "EXECUTION_ERROR")
        return PlatformResult(
            ok=process.returncode == 0,
            value={"stdout": stdout.decode("utf-8", errors="replace"),
                   "stderr": stderr.decode("utf-8", errors="replace"),
                   "exit_code": process.returncode},
            error=stderr.decode("utf-8", errors="replace") or None,
            error_code=None if process.returncode == 0 else "COMMAND_ERROR",
        )
