"""Real end-to-end tests of the PLUTO tools against this actual machine.

These tests execute the real tools (not mocks) through the registry and check
that effects are real and verified. They are environment-adaptive:

- Desktop tools (screenshot / volume / clipboard / GUI apps) depend on a real
  graphical session and installed utilities. Where the session is missing the
  tests assert the *honest* failure contract (a real error code, no fabricated
  success); where the session exists they assert real success with a verified
  side-effect.
- File and process tools run for real in a sandboxed folder under the home dir.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import uuid

import pytest

from app.tools.registry import get_registry
from app.tools.terminal_base import command_exists, resolve_session_env


def run_tool(tool_name: str, **kwargs):
    """Execute one real tool synchronously (registry instance is cached)."""
    tool = get_registry().get_tool(tool_name)
    assert tool is not None, f"{tool_name} is not registered"
    return asyncio.run(tool.execute(**kwargs))


def display_available() -> bool:
    return resolve_session_env() is not None


@pytest.fixture()
def sandbox_dir():
    """A fresh writable folder under ~/Documents (inside the sandbox)."""
    base = os.path.join(os.path.expanduser("~/Documents"), "PLUTO_e2e_tests")
    os.makedirs(base, exist_ok=True)
    folder = os.path.join(base, f"run_{uuid.uuid4().hex[:8]}")
    os.makedirs(folder)
    yield folder
    shutil.rmtree(folder, ignore_errors=True)
    if os.path.isdir(base) and not os.listdir(base):
        os.rmdir(base)


# ---------------------------------------------------------------------------
# Filesystem: real create -> read -> copy -> move -> find -> delete
# ---------------------------------------------------------------------------
def test_create_folder_and_file_are_real(sandbox_dir):
    folder = os.path.join(sandbox_dir, "Reports")
    res = run_tool("create_folder", path=folder)
    assert res.success and res.verification_passed
    assert os.path.isdir(folder)

    path = os.path.join(folder, "notes.txt")
    res = run_tool("create_file", path=path, content="hello pluto")
    assert res.success and res.verification_passed
    assert os.path.isfile(path)
    assert open(path, encoding="utf-8").read() == "hello pluto"


def test_read_file_returns_content(sandbox_dir):
    path = os.path.join(sandbox_dir, "readme.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("the quick brown fox")
    res = run_tool("read_file", path=path)
    assert res.success
    assert res.data["content"] == "the quick brown fox"


def test_list_directory_reports_entries(sandbox_dir):
    run_tool("create_file", path=os.path.join(sandbox_dir, "a.txt"), content="a")
    run_tool("create_file", path=os.path.join(sandbox_dir, "b.txt"), content="b")
    res = run_tool("list_directory", path=sandbox_dir)
    assert res.success
    names = {item["name"] for item in res.data["items"]}
    assert {"a.txt", "b.txt"} <= names


def test_copy_move_delete_verify_effects(sandbox_dir):
    src = os.path.join(sandbox_dir, "src.txt")
    copy = os.path.join(sandbox_dir, "copy.txt")
    moved = os.path.join(sandbox_dir, "moved.txt")
    run_tool("create_file", path=src, content="payload")

    res = run_tool("copy_file", source=src, destination=copy)
    assert res.success and res.verification_passed
    assert os.path.isfile(src) and os.path.isfile(copy)

    res = run_tool("move_file", source=copy, destination=moved)
    assert res.success and res.verification_passed
    assert not os.path.exists(copy) and os.path.isfile(moved)

    res = run_tool("delete_file", path=moved)
    assert res.success and res.verification_passed
    assert not os.path.exists(moved)
    assert os.path.isfile(src)  # untouched


def test_find_files_locates_real_file(sandbox_dir):
    path = os.path.join(sandbox_dir, "quarterly-report.pdf")
    run_tool("create_file", path=path, content="numbers")
    res = run_tool("find_files", query="quarterly", location=sandbox_dir)
    assert res.success
    files = [item["path"] if isinstance(item, dict) else item for item in res.data["files"]]
    assert path in files


def test_sandbox_blocks_outside_paths():
    res = run_tool("list_directory", path="/etc")
    assert not res.success
    assert res.error_code == "PERMISSION_DENIED"


def test_create_file_outside_sandbox_is_blocked():
    res = run_tool("create_file", path="/tmp/pluto_escape.txt", content="nope")
    assert not res.success
    assert not os.path.exists("/tmp/pluto_escape.txt")


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------
def test_execute_command_real_and_verified():
    res = run_tool("execute_command", command="echo hello-pluto")
    assert res.success
    assert "hello-pluto" in res.data["stdout"]


def test_execute_command_reports_real_error():
    res = run_tool("execute_command", command="ls /definitely/not/here")
    assert not res.success
    assert res.exit_code not in (None, 0)


# ---------------------------------------------------------------------------
# Processes
# ---------------------------------------------------------------------------
def test_get_processes_lists_self():
    res = run_tool("get_processes", name="python")
    assert res.success
    # The interpreter running this suite must be visible (idle processes too).
    assert res.data["count"] >= 1


def test_kill_process_does_not_fabricate_success():
    res = run_tool("kill_process", process="pluto-ghost-process-xyz")
    assert res.success  # nothing was running, so nothing needed killing
    assert res.data["was_running"] is False
    assert res.verification_passed


# ---------------------------------------------------------------------------
# Desktop tools: real success when the session exists, honest failure when not
# ---------------------------------------------------------------------------
HONEST_DISPLAY_CODES = {"NO_DISPLAY", "MISSING_DEPENDENCY"}


@pytest.mark.skipif(not display_available(), reason="no graphical session in this environment")
def test_screenshot_on_display_is_real_image():
    res = run_tool("take_screenshot")
    if res.success:
        assert res.verification_passed
        path = res.data["path"]
        assert os.path.isfile(path)
        with open(path, "rb") as fh:
            head = fh.read(8)
        assert head == b"\x89PNG\r\n\x1a\n" or head[:2] == b"\xff\xd8"
        os.unlink(path)
    else:
        assert res.error_code in HONEST_DISPLAY_CODES, res.error


def test_screenshot_without_display_is_honest():
    if display_available():
        pytest.skip("graphical session present; display-gating path not exercised")
    res = run_tool("take_screenshot")
    assert not res.success
    assert res.error_code == "NO_DISPLAY"


def test_clipboard_and_volume_honest_or_real():
    for tool_name, kwargs, good_code in (
        ("copy_to_clipboard", {"text": "pluto-test"}, "MISSING_DEPENDENCY"),
        ("get_clipboard", {}, "MISSING_DEPENDENCY"),
        ("get_volume", {}, "MISSING_DEPENDENCY"),
        ("set_volume", {"level": "mute"}, "MISSING_DEPENDENCY"),
    ):
        res = run_tool(tool_name, **kwargs)
        if res.success:
            assert res.verification_passed is True
        else:
            assert res.error_code in {"NO_DISPLAY", good_code}, (tool_name, res.error)


def test_open_application_never_fabricates():
    res = run_tool("open_application", application="pluto-no-such-app")
    assert not res.success
    assert res.error_code == "APP_NOT_FOUND"


def test_list_running_applications_is_safe_even_headless():
    res = run_tool("list_running_applications")
    assert res.success  # honest "none running" when headless is a valid result


# ---------------------------------------------------------------------------
# Browser: no fabricated navigation without a working browser
# ---------------------------------------------------------------------------
def test_open_url_without_browser_is_honest_error():
    if command_exists("google-chrome") or command_exists("chromium"):
        pytest.skip("a system browser exists; tool may legitimately succeed")
    res = run_tool("open_url", url="https://example.com")
    assert not res.success
    assert res.error_code in {"BROWSER_START_FAILED", "NO_DISPLAY", "MISSING_DEPENDENCY"}


# ---------------------------------------------------------------------------
# Messaging: configured provider required; never a fake "sent"
# ---------------------------------------------------------------------------
def test_send_message_requires_provider():
    if os.environ.get("PLUTO_MESSAGING_COMMAND"):
        pytest.skip("messaging provider configured")
    res = run_tool("send_message", recipient="alice", message="hello")
    assert not res.success
    assert res.error_code == "NOT_CONFIGURED"
