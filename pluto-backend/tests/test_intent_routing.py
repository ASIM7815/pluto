"""Intent routing tests: natural language -> the RIGHT real tool call(s).

These are pure planner tests (no execution). They pin the behaviour the task
cares about: synonyms must reach the same tool, multi-action requests must
produce ordered multi-tool plans, follow-ups must use context, and the intent
endpoint must recommend exactly what the planner would execute.
"""
from __future__ import annotations

import pytest

from app.agent.nlu import intent_planner
from app.llm.gpt_oss import GPTOSSClient, LLMToolCall
from app.tools.registry import get_registry

ALL_TOOLS = {t.name for t in get_registry().get_all_tools()}


def plan_first(command: str, context: dict | None = None) -> LLMToolCall:
    """First planned tool call for a command."""
    for item in GPTOSSClient._build_plan(command, context):
        if isinstance(item, LLMToolCall):
            return item
    raise AssertionError(f"No tool planned for: {command!r} -> {GPTOSSClient._build_plan(command)}")


def planned_tools(command: str, context: dict | None = None) -> list[str]:
    return [i.name for i in GPTOSSClient._build_plan(command, context) if isinstance(i, LLMToolCall)]


def test_planner_only_references_registered_tools():
    """Every planned tool must exist in the registry (never invent tools)."""
    sample_commands = [
        "take a screenshot", "capture my screen", "open YouTube, search for Iron Man, play second video",
        "set volume to 40", "copy hello to the clipboard", "create a folder called A in Documents",
        "run ls -la", "open firefox", "send a whatsapp message to Sam saying hi",
        "play the second video", "what's on my clipboard", "close the browser",
    ]
    for command in sample_commands:
        for item in GPTOSSClient._build_plan(command):
            if isinstance(item, LLMToolCall):
                assert item.name in ALL_TOOLS, f"{command!r} planned unknown tool {item.name}"


# ---------------------------------------------------------------------------
# Screenshot synonyms (the task calls these out explicitly)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("command", [
    "take a screenshot",
    "screenshot",
    "screenshot this",
    "capture my screen",
    "capture the screen",
    "capture a screenshot",
    "take a screen capture",
    "grab a screenshot",
    "snapshot of the screen",
    "take a picture of the screen",
    "print screen",
])
def test_screenshot_synonyms_route_to_tool(command: str):
    first = plan_first(command)
    assert first.name == "take_screenshot"
    assert first.arguments.get("area", "full") == "full"


def test_screenshot_variations_area_and_save_location():
    assert plan_first("take a screenshot of the window").arguments["area"] == "window"
    assert plan_first("screenshot the active window").arguments["area"] == "window"
    assert plan_first("take a screenshot and save it in my Documents folder").arguments == {
        "area": "full", "directory": "~/Documents",
    }
    shot = plan_first("screenshot the screen and save it to Downloads")
    assert shot.arguments["directory"] == "~/Downloads"


# ---------------------------------------------------------------------------
# The YouTube multi-action example from the task
# ---------------------------------------------------------------------------
def test_youtube_search_and_play_second_video_plan():
    steps = planned_tools("open YouTube, search for Iron Man, and play the second video")
    assert steps == ["open_url", "browser_search", "browser_click"]

    plan = GPTOSSClient._build_plan("open YouTube, search for Iron Man, and play the second video")
    calls = [i for i in plan if isinstance(i, LLMToolCall)]
    assert calls[0].arguments["url"] == "https://www.youtube.com"
    assert calls[1].arguments == {"query": "Iron Man", "site": "youtube"}
    assert calls[2].arguments == {"selector": "a#video-title", "index": 1}
    assert any(isinstance(i, str) and "second video" in i for i in plan)


def test_youtube_open_and_play_first_video():
    calls = [i for i in GPTOSSClient._build_plan("open YouTube and play Iron Man")
             if isinstance(i, LLMToolCall)]
    assert [c.name for c in calls] == ["open_url", "browser_search", "browser_click"]
    assert calls[2].arguments["index"] == 0


def test_play_second_video_followup_with_context():
    ctx = {"current_url": "https://www.youtube.com/results?search_query=iron+man",
           "current_page_title": "Iron Man - YouTube"}
    first = plan_first("play the second video", ctx)
    assert first.name == "browser_click"
    assert first.arguments == {"selector": "a#video-title", "index": 1}


def test_search_followup_uses_open_tab_context():
    ctx = {"current_url": "https://www.youtube.com/", "current_page_title": "YouTube"}
    first = plan_first("search Iron Man", ctx)
    assert first.name == "browser_search"
    assert first.arguments == {"query": "Iron Man", "site": "youtube"}


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("command,expected_app", [
    ("Open Firefox", "firefox"),
    ("Launch VS Code", "code"),
    ("open visual studio code", "code"),
    ("start the terminal", "gnome-terminal"),
    ("please open google chrome", "google-chrome"),
    ("run spotify", "spotify"),
])
def test_open_application_variants(command: str, expected_app: str):
    call = plan_first(command)
    assert call.name == "open_application"
    assert call.arguments["application"] == expected_app


@pytest.mark.parametrize("command,expected_app", [
    ("Close Chrome", "google-chrome"),
    ("Quit Slack", "slack"),
    ("Exit Firefox", "firefox"),
])
def test_close_application_variants(command: str, expected_app: str):
    call = plan_first(command)
    assert call.name == "close_application"
    assert call.arguments["application"] == expected_app


def test_switch_and_list_apps():
    assert plan_first("Switch to Terminal").name == "switch_to_application"
    assert plan_first("focus on Firefox").name == "switch_to_application"
    for q in ("what apps are running?", "list running applications", "show running apps"):
        call = plan_first(q)
        assert call.name == "list_running_applications"


def test_close_browser_uses_browser_tool():
    assert plan_first("close the browser").name == "close_browser"


# ---------------------------------------------------------------------------
# Websites / URLs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("command", ["open github", "go to reddit", "open example.com",
                                     "open https://news.ycombinator.com"])
def test_website_opens_in_browser(command: str):
    call = plan_first(command)
    assert call.name == "open_url"


def test_browser_snapshot_intent():
    assert plan_first("what's on the screen right now?").name == "browser_snapshot"


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------
def test_create_folder_plan_places_path():
    call = plan_first("create a folder called Reports in my Documents folder")
    assert call.name == "create_folder"
    assert call.arguments["path"].endswith("/Documents/Reports")


def test_create_file_plan_extracts_name_and_content():
    call = plan_first('create a file called notes.txt saying hello pluto')
    assert call.name == "create_file"
    assert call.arguments["path"].endswith("/notes.txt")
    assert call.arguments["content"] == "hello pluto"


def test_read_and_list_and_find():
    assert plan_first("read the file notes.txt").name == "read_file"
    assert plan_first("list files in my Downloads").name == "list_directory"
    call = plan_first("find files matching budget")
    assert call.name == "find_files"
    assert call.arguments["query"] == "budget"


def test_copy_and_move_plans():
    copy = plan_first("copy the file notes.txt from Documents to Downloads")
    assert copy.name == "copy_file"
    assert copy.arguments["source"].endswith("/Documents/notes.txt")
    assert copy.arguments["destination"].endswith("/Downloads/notes.txt")

    move = plan_first("move report.pdf from Downloads to Documents")
    assert move.name == "move_file"
    assert move.arguments["source"].endswith("/Downloads/report.pdf")
    assert move.arguments["destination"].endswith("/Documents/report.pdf")

    rename = plan_first("rename notes.txt to diary.txt")
    assert rename.name == "move_file"
    assert rename.arguments["source"].endswith("/notes.txt")
    assert rename.arguments["destination"].endswith("/diary.txt")


def test_delete_plan():
    call = plan_first("delete the file old-report.txt")
    assert call.name == "delete_file"


# ---------------------------------------------------------------------------
# System: volume / clipboard / processes / screenshot
# ---------------------------------------------------------------------------
def test_volume_intents():
    assert plan_first("set volume to 30").arguments == {"level": "30"}
    assert plan_first("turn the volume up to 50 percent").arguments == {"level": "50"}
    assert plan_first("mute the sound").arguments == {"level": "mute"}
    assert plan_first("unmute").arguments == {"level": "unmute"}
    assert plan_first("what is the volume?").name == "get_volume"
    assert plan_first("check the volume").name == "get_volume"


def test_clipboard_intents():
    call = plan_first("copy hello world to the clipboard")
    assert call.name == "copy_to_clipboard"
    assert call.arguments["text"] == "hello world"
    assert plan_first("what's on my clipboard?").name == "get_clipboard"


def test_process_intents():
    call = plan_first("is spotify running?")
    assert call.name == "get_processes"
    assert call.arguments.get("name") == "spotify"

    call2 = plan_first("stop the process named firefox")
    assert call2.name == "kill_process"
    assert call2.arguments.get("process") == "firefox"

    assert plan_first("show me the top processes").name == "get_processes"
    assert plan_first("check system status").name == "get_processes"


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------
def test_messaging_intents():
    call = plan_first("send a whatsapp message to Mom saying I will be late")
    assert call.name == "send_message"
    assert call.arguments["recipient"] == "mom"
    assert call.arguments["message"] == "I will be late"

    call2 = plan_first("telegram Sam that the build passed")
    assert call2.name == "send_message"
    assert call2.arguments["recipient"] == "sam"

    assert plan_first("open whatsapp").name == "open_chat_app"


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------
def test_terminal_intents():
    call = plan_first("run ls -la")
    assert call.name == "execute_command"
    assert call.arguments["command"] == "ls -la"
    call2 = plan_first("execute pwd in the terminal")
    assert call2.arguments["command"] == "pwd"


# ---------------------------------------------------------------------------
# No dead-ends: recognise more than the literal examples
# ---------------------------------------------------------------------------
def test_registry_recommendations_match_planner():
    registry = get_registry()
    cases = [
        ("take a screenshot and save it in Documents", "take_screenshot"),
        ("capture my screen", "take_screenshot"),
        ("open YouTube and search for Iron Man", "browser_search"),
        ("play the second video", "browser_click"),
        ("create a folder called X in Documents", "create_folder"),
        ("set volume to 40", "set_volume"),
        ("copy to the clipboard", "copy_to_clipboard"),
        ("run ls -la", "execute_command"),
        ("open firefox", "open_application"),
        ("send a whatsapp message to Mom saying hi", "send_message"),
        ("send a whatsapp message", "open_chat_app"),
        ("is spotify running", "get_processes"),
        ("stop the process named chrome", "kill_process"),
        ("read the file x.txt", "read_file"),
        ("close the browser", "close_browser"),
    ]
    for command, expected in cases:
        recs = registry.get_recommended_tools(command)
        assert expected in recs, f"{command!r}: {recs}"


def test_recommendations_do_not_fabricate():
    assert intent_planner.recommend("hello") == []
    assert intent_planner.recommend("how much wood would a woodchuck chuck") == []


def test_intent_analyze_endpoint_matches_planner():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r = client.post("/api/tools/intent/analyze",
                        json={"command": "take a screenshot and save it in my Documents folder"})
        assert r.status_code == 200
        body = r.json()
        assert "take_screenshot" in body["recommended_tools"]
