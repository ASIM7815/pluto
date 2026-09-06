"""Messaging tools for PLUTO.

PLUTO integrates with messaging backends through a *configured* provider:

1. **Command provider** (recommended for real usage): set
   ``PLUTO_MESSAGING_COMMAND`` to an executable. PLUTO runs it with two
   arguments: the recipient and the message text (plus a third optional
   provider name). Exit code 0 = delivered. Point this at signal-cli,
   a WhatsApp/Telegram bridge script, a Mattermost CLI, etc.

2. **Browser provider**: opens the chat web app (WhatsApp Web / Telegram Web)
   in the PLUTO browser and types the message in the chat of ``recipient``.
   Only works when browser automation is installed AND the user is logged in.

Without any provider, the tool fails honestly instead of pretending to send.
"""
from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.tools.terminal_base import (
    TerminalTool,
    ToolResult,
    SafetyLevel,
    command_exists,
)

logger = get_logger(__name__)

_WEB_APPS = {
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "signal": "https://signal.org",
}


def messaging_provider_available() -> bool:
    if settings.pluto_messaging_command:
        return command_exists(settings.pluto_messaging_command.split()[0])
    return False


async def _send_via_command(recipient: str, text: str) -> ToolResult:
    command = settings.pluto_messaging_command
    if not command:
        return ToolResult.fail(
            "send_message",
            "No messaging provider is configured. Set PLUTO_MESSAGING_COMMAND "
            "in the backend .env to a script that delivers messages (see app/tools/messaging.py).",
            error_code="NOT_CONFIGURED",
        )
    argv = shlex.split(command)
    if not command_exists(argv[0]):
        return ToolResult.fail(
            "send_message",
            f"The configured messaging command '{argv[0]}' was not found.",
            error_code="MISSING_DEPENDENCY",
        )
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, recipient, text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    except asyncio.TimeoutError:
        return ToolResult.fail("send_message", "The messaging command timed out.", error_code="TIMEOUT")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail("send_message", f"Messaging command error: {e}", error_code="EXECUTION_ERROR")

    if process.returncode != 0:
        err_text = stderr.decode("utf-8", errors="replace").strip() or "exit " + str(process.returncode)
        return ToolResult.fail(
            "send_message", f"The messaging command failed: {err_text}", error_code="SEND_FAILED"
        )
    out = stdout.decode("utf-8", errors="replace").strip()
    return ToolResult.ok(
        "send_message",
        message=f"Message sent to {recipient}." + (f" {out}" if out else ""),
        data={"recipient": recipient, "length": len(text), "provider": "command"},
        verification_passed=True,
    )


async def _send_via_browser(recipient: str, text: str, app: str = "whatsapp") -> ToolResult:
    from app.tools.browser import browser_manager

    if not browser_manager.available:
        return ToolResult.fail(
            "send_message",
            "Browser messaging needs Playwright + Chromium installed and a "
            "logged-in chat session (see app/tools/browser.py).",
            error_code="MISSING_DEPENDENCY",
        )
    url = _WEB_APPS.get(app.lower(), _WEB_APPS["whatsapp"])
    nav = await browser_manager.navigate(url)
    if not nav.success:
        return ToolResult.fail("send_message", nav.message, error_code="NAV_FAILED")

    # Chat apps expose a global search box; type the recipient, open the chat.
    try:
        search_box = None
        for sel in ("div[contenteditable='true']", "input[type='text']", "[role='textbox']"):
            count = await browser_manager._page.locator(sel).count() if browser_manager._page else 0
            if count:
                search_box = browser_manager._page.locator(sel).first
                break
        if search_box is None:
            return ToolResult.fail(
                "send_message",
                "Could not find the chat search box - are you logged in to the chat app?",
                error_code="NOT_LOGGED_IN",
            )
        await search_box.click(timeout=5000)
        await search_box.fill("")
        await search_box.type(recipient, delay=40)
        await browser_manager._page.keyboard.press("Enter")
        await asyncio.sleep(1.2)
        # Message box is typically the last contenteditable; type + Enter.
        boxes = browser_manager._page.locator("div[contenteditable='true']")
        count = await boxes.count()
        if count == 0:
            return ToolResult.fail(
                "send_message", "Chat opened but no message box was found.", error_code="SEND_FAILED"
            )
        msg_box = boxes.nth(count - 1)
        await msg_box.click(timeout=5000)
        await msg_box.type(str(text), delay=25)
        await browser_manager._page.keyboard.press("Enter")
    except Exception as e:  # noqa: BLE001
        return ToolResult.fail("send_message", f"Sending failed: {e}", error_code="SEND_FAILED")

    return ToolResult.ok(
        "send_message",
        message=f"Message sent to {recipient}.",
        data={"recipient": recipient, "provider": f"browser:{app.lower()}"},
        verification_passed=True,
    )


class SendMessageTool(TerminalTool):
    """Send a message through the configured messaging provider."""

    name = "send_message"
    description = (
        "Sends a chat message to a recipient through the configured messaging "
        "provider (see PLUTO_MESSAGING_COMMAND or the chat web app). Use for "
        "'send Owais a message ...' style commands."
    )
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    category = "message"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Recipient name or number"},
                "message": {"type": "string", "description": "Message text"},
                "provider": {
                    "type": "string",
                    "description": "Optional: 'command' or 'browser:whatsapp'",
                    "default": "command",
                },
            },
            "required": ["recipient", "message"],
        }

    async def execute(
        self, recipient: str, message: str, provider: str = "command", **kwargs
    ) -> ToolResult:
        if not recipient or not message:
            return ToolResult.fail(
                self.name, "Both a recipient and a message are required.", error_code="BAD_ARGUMENTS"
            )
        provider = (provider or "command").lower()
        if provider.startswith("browser"):
            app = provider.split(":", 1)[1] if ":" in provider else "whatsapp"
            return await _send_via_browser(recipient, message, app)
        return await _send_via_command(recipient, message)


class OpenChatAppTool(TerminalTool):
    """Open a chat app in the browser."""

    name = "open_chat_app"
    description = "Opens a chat application (whatsapp, telegram, signal) in the browser."
    safety_level = SafetyLevel.SAFE
    category = "message"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "whatsapp | telegram | signal", "default": "whatsapp"}
            },
            "required": ["app"],
        }

    async def execute(self, app: str = "whatsapp", **kwargs) -> ToolResult:
        url = _WEB_APPS.get((app or "whatsapp").lower())
        if not url:
            return ToolResult.fail(
                self.name, f"Unknown chat app '{app}'.", error_code="BAD_ARGUMENTS"
            )
        from app.tools.browser import browser_manager
        return await browser_manager.navigate(url)


MESSAGING_TOOLS: List[TerminalTool] = [
    SendMessageTool(),
    OpenChatAppTool(),
]
