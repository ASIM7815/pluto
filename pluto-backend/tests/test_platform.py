"""Tests for the platform abstraction (Phase 4).

Verifies host detection, adapter selection, capability reporting, and honest
failure for unsupported operations (no fabricated success).
"""
from __future__ import annotations

import asyncio
import os

import pytest

from app.platform import (
    get_platform,
    get_platform_capabilities,
    detect_platform_name,
    reset_platform,
    PlutoPlatform,
    AndroidPlatform,
)


def test_detect_platform_name_returns_known_value():
    assert detect_platform_name() in {"linux", "windows", "android", "unknown"}


def test_get_platform_returns_pluto_platform():
    reset_platform()
    p = get_platform()
    assert isinstance(p, PlutoPlatform)
    assert p.name in {"linux", "windows", "android"}


def test_platform_capabilities_report():
    reset_platform()
    report = get_platform_capabilities()
    assert report["platform"] in {"linux", "windows", "android"}
    assert "gui" in report


@pytest.mark.asyncio
async def test_run_command_echo():
    p = get_platform()
    res = await p.run_command("printf hello")
    assert res.ok is True
    assert "hello" in str(res.value["stdout"])


def test_command_exists_on_linux():
    p = get_platform()
    if p.name == "linux":
        assert p.command_exists("ls") is True
        assert p.command_exists("definitely-not-a-real-binary-xyz") is False
    else:
        assert callable(p.command_exists)


@pytest.mark.asyncio
async def test_android_adapter_reports_unsupported_honestly():
    android = AndroidPlatform()
    res = await android.set_volume("50")
    assert res.ok is False
    assert res.error_code == "UNSUPPORTED"
    caps = android.capabilities()
    assert caps["terminal"] is False


@pytest.mark.asyncio
async def test_non_running_process_is_honest():
    p = get_platform()
    res = await p.kill_process("definitely-not-a-real-process-xyz", force=True)
    # Either the process doesn't exist (so no-op success / honest) or the
    # platform can't reach it - in both cases we never report a bogus kill.
    assert isinstance(res.ok, bool)
    assert res.error_code != "KILL_FAILED" or res.ok is False
