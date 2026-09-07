"""Regression tests for all four Level-1 application-management intents."""
from app.llm.gpt_oss import GPTOSSClient
from app.tools.registry import get_registry


def _first_call(command: str):
    plan = GPTOSSClient._build_plan(command)
    assert plan
    return plan[0]


def test_mock_planner_supports_every_application_action():
    cases = {
        "Open Firefox": ("open_application", "firefox"),
        "Launch VS Code": ("open_application", "code"),
        "Close Chrome": ("close_application", "google-chrome"),
        "Quit Slack": ("close_application", "slack"),
        "Switch to Terminal": ("switch_to_application", "gnome-terminal"),
        "Focus on Firefox": ("switch_to_application", "firefox"),
    }
    for command, (tool, application) in cases.items():
        call = _first_call(command)
        assert call.name == tool, command
        assert call.arguments["application"] == application, command


def test_mock_planner_lists_running_apps():
    for command in ("What apps are running?", "List running applications"):
        call = _first_call(command)
        assert call.name == "list_running_applications"
        assert call.arguments == {}


def test_registry_recommends_all_application_tools():
    registry = get_registry()
    cases = {
        "open Firefox": "open_application",
        "close Chrome": "close_application",
        "switch to Terminal": "switch_to_application",
        "what apps are running?": "list_running_applications",
    }
    for command, expected in cases.items():
        assert expected in registry.get_recommended_tools(command), command
