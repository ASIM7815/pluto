"""PLUTO platform abstraction.

One shared core + per-OS adapters, so PLUTO can run on Linux (primary), Windows
and (where technically possible) Android while keeping all the *agent
intelligence* identical. Platform-specific operations (opening apps, volume,
clipboard, screenshots, processes) live in separate adapter files.

Every adapter returns a :class:`PlatformResult` with an honest ``ok`` flag and an
``error``/``error_code`` when something isn't supported or failed - PLUTO never
fabricates a success. The base class also declares a capability report so the UI
and the packaging layer know what the current platform can actually do.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlatformResult:
    """Canonical result shape for a platform operation."""

    ok: bool
    value: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None

    @classmethod
    def success(cls, value: Any = None) -> "PlatformResult":
        return cls(ok=True, value=value)

    @classmethod
    def fail(cls, message: str, error_code: str = "UNSUPPORTED") -> "PlatformResult":
        return cls(ok=False, error=message, error_code=error_code)


class PlutoPlatform(abc.ABC):
    """Abstract base for a concrete operating-system adapter."""

    #: Display name (e.g. "linux", "windows", "android").
    name: str = "unknown"

    @abc.abstractmethod
    def available(self) -> bool:
        """Whether this adapter can run on the current host."""

    @abc.abstractmethod
    def is_gui_available(self) -> bool:
        """Whether a graphical session is reachable (True on a normal desktop)."""

    @abc.abstractmethod
    def env_for_session(self) -> Optional[Dict[str, str]]:
        """Environment vars needed to reach the user's session (e.g. DISPLAY)."""

    # --- executables -----------------------------------------------------
    @abc.abstractmethod
    def command_exists(self, command: str) -> bool:
        """Whether ``command`` resolves to an executable on PATH."""

    # --- apps / files -----------------------------------------------------
    @abc.abstractmethod
    async def open_app(self, application: str, arguments: Optional[List[str]] = None) -> PlatformResult:
        """Launch a desktop application."""

    @abc.abstractmethod
    async def open_file(self, path: str) -> PlatformResult:
        """Open a file with the default application."""

    @abc.abstractmethod
    async def open_folder(self, path: str) -> PlatformResult:
        """Open a folder in the file manager."""

    # --- processes --------------------------------------------------------
    @abc.abstractmethod
    async def is_process_running(self, name: str) -> bool:
        """Whether a process by that name is running."""

    @abc.abstractmethod
    async def list_processes(self, limit: int = 25) -> PlatformResult:
        """List running processes (best-effort)."""

    @abc.abstractmethod
    async def kill_process(self, name: str, force: bool = False) -> PlatformResult:
        """Terminate a process; honest 'not running' if absent."""

    # --- system: volume / clipboard / screenshot ---------------------------
    @abc.abstractmethod
    async def get_volume(self) -> PlatformResult:
        """Read the current volume level."""

    @abc.abstractmethod
    async def set_volume(self, level: str) -> PlatformResult:
        """Set volume / mute / unmute."""

    @abc.abstractmethod
    async def get_clipboard(self) -> PlatformResult:
        """Read clipboard text."""

    @abc.abstractmethod
    async def set_clipboard(self, text: str) -> PlatformResult:
        """Write text to the clipboard."""

    @abc.abstractmethod
    async def take_screenshot(self, area: str, destination: str) -> PlatformResult:
        """Capture the screen; returns the written path in ``value`` on success."""

    @abc.abstractmethod
    async def run_command(
        self,
        command: Any,
        shell: bool = False,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> PlatformResult:
        """Run a system command and return (stdout, stderr, exit_code)."""

    # ------------------------------------------------------------------
    def capabilities(self) -> Dict[str, Any]:
        """A machine-readable report of what this platform supports."""
        return {
            "name": self.name,
            "gui": self.is_gui_available(),
            "apps": True,
            "files": True,
            "processes": True,
            "volume": True,
            "clipboard": True,
            "screenshot": True,
            "terminal": True,
        }
