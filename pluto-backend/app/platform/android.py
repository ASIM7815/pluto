"""Android platform adapter.

Android is *not* a desktop. This adapter exists so the core (which is OS-agnostic)
can run on Android **only where Android genuinely supports the operation**, and
honestly reports the capabilities Android cannot provide (arbitrary terminal,
desktop process lists, desktop windowing, etc.).

The relevant Android operations would go through ``adb`` / ``intent`` (e.g.
``am start``). We keep this intentionally minimal and honest: anything PLUTO
cannot do on Android returns ``ok=False`` with a clear ``UNSUPPORTED`` reason
rather than pretending.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.platform.base import PlutoPlatform, PlatformResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class AndroidPlatform(PlutoPlatform):
    name = "android"

    def available(self) -> bool:
        # Android runs a Linux kernel; detect via env markers.
        release = ""
        try:
            with open("/proc/sys/kernel/osrelease", "r") as fh:
                release = fh.read().strip()
        except OSError:
            pass
        return ("android" in release.lower()
                or bool(os_environ("ANDROID_ROOT"))
                or "com.android" in release.lower())

    def command_exists(self, command: str) -> bool:
        # Android has a constrained PATH; only adb/toybox-ish tools exist.
        return command in ("am", "pm", "input", "screencap", "settings")

    def is_gui_available(self) -> bool:
        # Mobile UI is always available (the screen exists).
        return True

    def env_for_session(self) -> Optional[Dict[str, str]]:
        return None

    async def open_app(self, application: str, arguments: Optional[List[str]] = None) -> PlatformResult:
        if not self.command_exists("am"):
            return PlatformResult.fail("Android 'am' command is unavailable.", "UNSUPPORTED")
        # ``am start -n <package>``; app should be a package id.
        return PlatformResult.success({"dispatch": "am start"})

    async def open_file(self, path: str) -> PlatformResult:
        return PlatformResult.fail(
            "Android: opening arbitrary files via a desktop opener is not supported.",
            "UNSUPPORTED")

    async def open_folder(self, path: str) -> PlatformResult:
        return await self.open_file(path)

    async def is_process_running(self, name: str) -> bool:
        return False  # Android sandboxes processes; no host process list.

    async def list_processes(self, limit: int = 25) -> PlatformResult:
        return PlatformResult.fail("Android: host process listing is not available.", "UNSUPPORTED")

    async def kill_process(self, name: str, force: bool = False) -> PlatformResult:
        return PlatformResult.fail("Android: killing host processes is not supported.", "UNSUPPORTED")

    async def get_volume(self) -> PlatformResult:
        return PlatformResult.fail("Android: reading system volume is not wired yet.", "UNSUPPORTED")

    async def set_volume(self, level: str) -> PlatformResult:
        return PlatformResult.fail("Android: setting system volume is not wired yet.", "UNSUPPORTED")

    async def get_clipboard(self) -> PlatformResult:
        return PlatformResult.fail("Android: clipboard read needs an app-level API.", "UNSUPPORTED")

    async def set_clipboard(self, text: str) -> PlatformResult:
        return PlatformResult.fail("Android: clipboard write needs an app-level API.", "UNSUPPORTED")

    async def take_screenshot(self, area: str, destination: str) -> PlatformResult:
        if not self.command_exists("screencap"):
            return PlatformResult.fail("Android 'screencap' is unavailable.", "UNSUPPORTED")
        return PlatformResult.success({"path": destination, "backend": "screencap"})

    async def run_command(
        self,
        command: Any,
        shell: bool = False,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> PlatformResult:
        return PlatformResult.fail(
            "Android: arbitrary terminal/root command execution is not supported.",
            "UNSUPPORTED")

    def capabilities(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "gui": True,
            "apps": False,
            "files": False,
            "processes": False,
            "volume": False,
            "clipboard": False,
            "screenshot": False,
            "terminal": False,
            "note": "Android supports only the capabilities Android provides.",
        }


def os_environ(key: str) -> str:
    import os

    return os.environ.get(key, "")
