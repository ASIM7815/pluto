"""PLUTO platform abstraction (Linux / Windows / Android).

The core intelligence is fully OS-agnostic. This package selects the adapter for
the current host so the same core can be packaged for Linux (.deb), Windows
(.exe) and, where Android genuinely supports it, Android.

Typical use::

    from app.platform import get_platform

    platform = get_platform()
    if platform.is_gui_available():
        ...
"""

from __future__ import annotations

import os
import platform as _platform
from typing import Optional

from .base import PlutoPlatform, PlatformResult
from .linux import LinuxPlatform
from .windows import WindowsPlatform
from .android import AndroidPlatform

__all__ = [
    "PlutoPlatform",
    "PlatformResult",
    "LinuxPlatform",
    "WindowsPlatform",
    "AndroidPlatform",
    "get_platform",
]

_ADAPTERS = {
    "linux": LinuxPlatform,
    "windows": WindowsPlatform,
    "android": AndroidPlatform,
}

_platform_instance: Optional[PlutoPlatform] = None


def detect_platform_name() -> str:
    """Return 'linux' | 'windows' | 'android' | 'unknown' for this host."""
    system = _platform.system().lower()
    release = _platform.release().lower()
    if "android" in release or os.environ.get("ANDROID_ROOT"):
        return "android"
    if system == "windows" or system.startswith("win"):
        return "windows"
    if system == "linux":
        return "linux"
    return "unknown"


def get_platform() -> PlutoPlatform:
    """Return the singleton adapter for the current host."""
    global _platform_instance
    if _platform_instance is None:
        name = detect_platform_name()
        adapter_cls = _ADAPTERS.get(name, LinuxPlatform)
        _platform_instance = adapter_cls()
    return _platform_instance


def reset_platform() -> None:
    """Clear the cached adapter (used by tests)."""
    global _platform_instance
    _platform_instance = None


def get_platform_capabilities() -> dict:
    """Platform + capability report (for the UI / health / packaging)."""
    p = get_platform()
    return {"platform": p.name, **p.capabilities()}
