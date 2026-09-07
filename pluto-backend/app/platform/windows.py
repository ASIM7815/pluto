"""Windows platform adapter (PowerShell-backed).

Shares the same core intelligence as Linux; OS-specific operations run through
PowerShell (``powershell -NoProfile -Command ...``). Runs on the build host.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import shlex
import subprocess  # noqa: F401
from typing import Any, Dict, List, Optional

from app.platform.base import PlutoPlatform, PlatformResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class WindowsPlatform(PlutoPlatform):
    name = "windows"

    def available(self) -> bool:
        return os.name == "nt" or shutil.which("powershell") is not None

    def command_exists(self, command: str) -> bool:
        return shutil.which(command) is not None

    def is_gui_available(self) -> bool:
        # Windows always has a desktop session available to the user.
        return True

    def env_for_session(self) -> Optional[Dict[str, str]]:
        return None

    async def _ps(self, script: str) -> PlatformResult:
        return await self.run_command(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            timeout=45,
        )

    async def open_app(self, application: str, arguments: Optional[List[str]] = None) -> PlatformResult:
        # ``Start-Process`` launches the app (by name or path) and returns.
        args = " ".join(shlex.quote(str(a)) for a in (arguments or []))
        ps = f"Start-Process -FilePath '{application}' {args}; exit 0"
        res = await self.run_command(["powershell", "-NoProfile", "-Command", ps])
        return PlatformResult.success({"process": application}) if res.ok else res

    async def open_file(self, path: str) -> PlatformResult:
        if self.command_exists("start"):
            return await self.run_command(["cmd", "/c", "start", "", os.path.expanduser(path)])
        return PlatformResult.fail("No default file opener available.", "MISSING_DEPENDENCY")

    async def open_folder(self, path: str) -> PlatformResult:
        return await self.open_file(path)

    async def is_process_running(self, name: str) -> bool:
        res = await self._ps(f"Get-Process -Name '{name}' -ErrorAction SilentlyContinue | Select-Object -First 1")
        return res.ok and bool(str(res.value.get("stdout", "")).strip())

    async def list_processes(self, limit: int = 25) -> PlatformResult:
        res = await self._ps(
            "Get-Process | Sort-Object CPU -Descending | Select-Object -First "
            f"{max(1, int(limit))} Id,ProcessName,CPU | Format-Table -HideTableHeaders"
        )
        rows = []
        for line in str(res.value.get("stdout", "")).splitlines():
            parts = line.split()
            if len(parts) >= 2:
                rows.append({"pid": parts[0], "name": parts[1], "cpu_percent": parts[-1]})
        return PlatformResult.success(rows) if res.ok else res

    async def kill_process(self, name: str, force: bool = False) -> PlatformResult:
        if not await self.is_process_running(name):
            return PlatformResult.success({"was_running": False})
        ps = f"Stop-Process -Name '{name}' -Force; exit 0" if force else \
             f"Stop-Process -Name '{name}'; exit 0"
        res = await self._ps(ps)
        return PlatformResult.success({"was_running": True}) if res.ok else res

    async def get_volume(self) -> PlatformResult:
        res = await self._ps(
            "(Get-AudioVolume -ErrorAction SilentlyContinue).Volume"
        )
        val = str(res.value.get("stdout", "")).strip()
        if res.ok and val.isdigit():
            return PlatformResult.success(int(val))
        return PlatformResult.fail("Could not read Windows volume.", "VOLUME_READ_FAILED")

    async def set_volume(self, level: str) -> PlatformResult:
        raw = str(level).strip().lower()
        if raw in ("mute", "unmute"):
            return PlatformResult.fail("Windows mute via PowerShell is not implemented; use the OS mixer.", "UNSUPPORTED")
        try:
            val = int(raw.rstrip("%"))
        except ValueError:
            return PlatformResult.fail(f"'{level}' is not a valid volume.", "BAD_ARGUMENTS")
        res = await self._ps(f"(Get-AudioVolume -ErrorAction SilentlyContinue).Volume = {val}")
        return PlatformResult.success({"level": val}) if res.ok else res

    async def get_clipboard(self) -> PlatformResult:
        res = await self._ps("Get-Clipboard")
        return PlatformResult.success(str(res.value.get("stdout", ""))) if res.ok else res

    async def set_clipboard(self, text: str) -> PlatformResult:
        # Escape embedded quote nastiness safely through a temp-free path.
        safe = text.replace("\"", "\"\"")
        res = await self._ps(f"Set-Clipboard -Value \"{safe}\"")
        return PlatformResult.success({"written": len(text)}) if res.ok else res

    async def take_screenshot(self, area: str, destination: str) -> PlatformResult:
        # PowerShell System.Drawing screen capture (full screen only).
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen; "
            "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height; "
            "$g=[System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size); "
            f"$bmp.Save('{os.path.expanduser(destination)}'); exit 0"
        )
        res = await self._ps(ps)
        if res.ok and os.path.isfile(os.path.expanduser(destination)):
            return PlatformResult.success({"path": os.path.expanduser(destination), "backend": "powershell"})
        return res if not res.ok else PlatformResult.fail("Screenshot capture failed.", "SCREENSHOT_FAILED")

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
                argv = list(command) if isinstance(command, (list, tuple)) else shlex.split(command)
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
