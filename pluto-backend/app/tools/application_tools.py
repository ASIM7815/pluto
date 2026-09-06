"""Application Management Tools - Open, close, switch applications using terminal"""
import shlex
from typing import Optional, Dict, Any, List
from app.tools.terminal_base import TerminalTool, ToolResult, SafetyLevel, VerificationMixin
from app.core.logging import get_logger

logger = get_logger(__name__)


# Common Linux applications and their executables
APP_MAPPINGS = {
    # Browsers
    "firefox": "firefox",
    "chrome": "google-chrome",
    "chromium": "chromium",
    "brave": "brave-browser",
    "edge": "microsoft-edge",
    
    # Code Editors
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "sublime": "subl",
    "atom": "atom",
    "vim": "vim",
    "emacs": "emacs",
    
    # File Managers
    "files": "nautilus",
    "file manager": "nautilus",
    "dolphin": "dolphin",
    "thunar": "thunar",
    
    # Terminals
    "terminal": "gnome-terminal",
    "konsole": "konsole",
    "xterm": "xterm",
    "alacritty": "alacritty",
    
    # Communication
    "slack": "slack",
    "discord": "discord",
    "telegram": "telegram-desktop",
    "zoom": "zoom",
    "teams": "teams",
    
    # Productivity
    "libreoffice": "libreoffice",
    "writer": "libreoffice --writer",
    "calc": "libreoffice --calc",
    "gimp": "gimp",
    "inkscape": "inkscape",
    "obs": "obs",
    
    # Media
    "vlc": "vlc",
    "spotify": "spotify",
    "audacity": "audacity",
}


class OpenApplicationTool(TerminalTool, VerificationMixin):
    """Open an application"""
    
    name = "open_application"
    description = "Opens an application on the desktop. Works for browsers, editors, file managers, and other GUI applications."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": "Application name (e.g., 'firefox', 'vscode', 'spotify')"
                }
            },
            "required": ["application"]
        }
    
    async def execute(self, application: str, **kwargs) -> ToolResult:
        """
        Open an application
        
        Args:
            application: Application name
            
        Returns:
            ToolResult
        """
        # Normalize application name
        app_lower = application.lower().strip()
        
        # Get executable name
        executable = APP_MAPPINGS.get(app_lower, app_lower)
        
        # Check if already running
        process_name = executable.split()[0]  # Get base command
        already_running = await self.check_process_running(process_name)
        
        if already_running:
            logger.info("application_already_running", app=application)
            return ToolResult(
                success=True,
                message=f"{application} is already running",
                data={"already_running": True},
                context_updates={"current_app": process_name}
            )
        
        # Launch application in background
        result = await self.run_command(
            f"{executable} &",
            shell=True,
            check_exit_code=False  # Background process returns immediately
        )
        
        # Give it a moment to start
        import asyncio
        await asyncio.sleep(1)
        
        # Verify it started
        is_running = await self.verify_process_started(process_name, timeout=5)
        
        if is_running:
            logger.info("application_opened", app=application, executable=executable)
            return ToolResult(
                success=True,
                message=f"Opened {application}",
                output=f"Process {process_name} started",
                verification_passed=True,
                data={"process_name": process_name, "executable": executable},
                context_updates={"current_app": process_name}
            )
        else:
            logger.warning("application_open_failed", app=application)
            return ToolResult(
                success=False,
                message=f"Failed to open {application}",
                error=f"Process {process_name} did not start",
                verification_passed=False
            )
    
    async def verify(self, result: ToolResult, application: str, **kwargs) -> bool:
        """Verify application opened"""
        if not result.success:
            return False
        
        process_name = result.data.get("process_name") if result.data else None
        if not process_name:
            return False
        
        return await self.check_process_running(process_name)


class CloseApplicationTool(TerminalTool, VerificationMixin):
    """Close an application"""
    
    name = "close_application"
    description = "Closes a running application gracefully. Use for applications you want to terminate."
    safety_level = SafetyLevel.CONFIRM_REQUIRED  # Ask before closing
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": "Application name to close"
                },
                "force": {
                    "type": "boolean",
                    "description": "Force kill if graceful close fails",
                    "default": False
                }
            },
            "required": ["application"]
        }
    
    async def execute(self, application: str, force: bool = False, **kwargs) -> ToolResult:
        """
        Close an application
        
        Args:
            application: Application name
            force: Force kill if needed
            
        Returns:
            ToolResult
        """
        # Get process name
        app_lower = application.lower().strip()
        executable = APP_MAPPINGS.get(app_lower, app_lower)
        process_name = executable.split()[0]
        
        # Check if running
        is_running = await self.check_process_running(process_name)
        if not is_running:
            return ToolResult(
                success=True,
                message=f"{application} is not running",
                data={"was_running": False}
            )
        
        # Try graceful close first (SIGTERM)
        result = await self.run_command(
            f"pkill {process_name}",
            check_exit_code=False
        )
        
        # Wait for process to end
        import asyncio
        await asyncio.sleep(2)
        
        # Check if closed
        still_running = await self.check_process_running(process_name)
        
        if not still_running:
            logger.info("application_closed", app=application, method="graceful")
            return ToolResult(
                success=True,
                message=f"Closed {application}",
                output="Process terminated gracefully",
                verification_passed=True,
                context_updates={"current_app": None}
            )
        
        # If force enabled and still running, kill it
        if force:
            await self.run_command(
                f"pkill -9 {process_name}",
                check_exit_code=False
            )
            await asyncio.sleep(1)
            
            still_running = await self.check_process_running(process_name)
            if not still_running:
                logger.info("application_closed", app=application, method="force_kill")
                return ToolResult(
                    success=True,
                    message=f"Force closed {application}",
                    output="Process force killed",
                    verification_passed=True,
                    context_updates={"current_app": None}
                )
        
        logger.warning("application_close_failed", app=application)
        return ToolResult(
            success=False,
            message=f"Failed to close {application}",
            error="Process still running",
            verification_passed=False
        )


class SwitchToApplicationTool(TerminalTool, VerificationMixin):
    """Switch to (focus) an application window"""
    
    name = "switch_to_application"
    description = "Switches focus to an application window. Brings the application to the foreground."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": "Application name to switch to"
                }
            },
            "required": ["application"]
        }
    
    async def execute(self, application: str, **kwargs) -> ToolResult:
        """
        Switch to application window
        
        Args:
            application: Application name
            
        Returns:
            ToolResult
        """
        # Get process name
        app_lower = application.lower().strip()
        executable = APP_MAPPINGS.get(app_lower, app_lower)
        process_name = executable.split()[0]
        
        # Check if running
        is_running = await self.check_process_running(process_name)
        if not is_running:
            return ToolResult(
                success=False,
                message=f"{application} is not running. Cannot switch to it.",
                error="Application not running"
            )
        
        # Try wmctrl first (most reliable)
        result = await self.run_command(
            f"wmctrl -a {shlex.quote(application)}",
            check_exit_code=False
        )
        
        if result.success or result.exit_code == 0:
            logger.info("window_switched", app=application, method="wmctrl")
            return ToolResult(
                success=True,
                message=f"Switched to {application}",
                output="Window activated",
                verification_passed=True,
                context_updates={"current_app": process_name, "active_window": application}
            )
        
        # Fallback: Try xdotool
        result = await self.run_command(
            f"xdotool search --name {shlex.quote(application)} windowactivate",
            shell=True,
            check_exit_code=False
        )
        
        if result.success:
            logger.info("window_switched", app=application, method="xdotool")
            return ToolResult(
                success=True,
                message=f"Switched to {application}",
                output="Window activated",
                verification_passed=True,
                context_updates={"current_app": process_name, "active_window": application}
            )
        
        logger.warning("window_switch_failed", app=application)
        return ToolResult(
            success=False,
            message=f"Failed to switch to {application}",
            error="Could not find or activate window"
        )


class ListRunningApplicationsTool(TerminalTool):
    """List all running GUI applications"""
    
    name = "list_running_applications"
    description = "Lists all currently running GUI applications with window titles."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        List running applications
        
        Returns:
            ToolResult with list of applications
        """
        # Use wmctrl to list windows
        result = await self.run_command(
            "wmctrl -l -p",
            check_exit_code=False
        )
        
        if not result.success or not result.output:
            # Fallback: use ps to list GUI processes
            result = await self.run_command(
                "ps aux | grep -E 'firefox|chrome|code|nautilus|terminal' | grep -v grep",
                shell=True,
                check_exit_code=False
            )
        
        apps = []
        if result.output:
            for line in result.output.split('\n'):
                if line.strip():
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        apps.append({
                            "window_id": parts[0],
                            "desktop": parts[1],
                            "pid": parts[2],
                            "title": parts[4] if len(parts) > 4 else "Unknown"
                        })
        
        logger.info("applications_listed", count=len(apps))
        return ToolResult(
            success=True,
            message=f"Found {len(apps)} running applications",
            output=result.output,
            data={"applications": apps, "count": len(apps)},
            context_updates={"running_apps": [app["title"] for app in apps]}
        )


# Register all tools
APPLICATION_TOOLS = [
    OpenApplicationTool(),
    CloseApplicationTool(),
    SwitchToApplicationTool(),
    ListRunningApplicationsTool(),
]
