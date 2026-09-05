"""Application control tools"""
import subprocess
import shlex
from typing import Dict, Optional
from app.core.logging import get_logger
from app.schemas.tools import ToolResult

logger = get_logger(__name__)


class ApplicationTools:
    """Launch and control applications"""
    
    # Application registry
    APP_REGISTRY = {
        "code": "code",
        "vscode": "code",
        "vs code": "code",
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium-browser",
        "nautilus": "nautilus",
        "files": "nautilus",
        "terminal": "gnome-terminal",
        "gedit": "gedit",
        "calculator": "gnome-calculator",
        "settings": "gnome-control-center",
        "spotify": "spotify",
        "discord": "discord",
        "slack": "slack",
        "vlc": "vlc",
    }
    
    @staticmethod
    async def open_application(
        application: str,
        arguments: Optional[list] = None,
        workspace: Optional[str] = None
    ) -> ToolResult:
        """Launch an application"""
        try:
            app_lower = application.lower().strip()
            
            # Look up in registry
            executable = ApplicationTools.APP_REGISTRY.get(app_lower, application)
            
            cmd = [executable]
            
            # Add workspace/path if provided
            if workspace:
                cmd.append(workspace)
            
            # Add additional arguments
            if arguments:
                cmd.extend(arguments)
            
            logger.info("launching_app", app=executable, cmd=cmd)
            
            # Launch process in background
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            return ToolResult(
                success=True,
                tool="open_application",
                message=f"Launched {executable}",
                data={
                    "application": executable,
                    "pid": process.pid,
                    "workspace": workspace
                }
            )
            
        except FileNotFoundError:
            return ToolResult(
                success=False,
                tool="open_application",
                error={
                    "code": "APP_NOT_FOUND",
                    "message": f"Application not found: {application}"
                }
            )
        except Exception as e:
            logger.error("app_launch_error", app=application, error=str(e))
            return ToolResult(
                success=False,
                tool="open_application",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )
    
    @staticmethod
    async def open_url(url: str) -> ToolResult:
        """Open URL in default browser"""
        try:
            import webbrowser
            webbrowser.open(url)
            
            logger.info("url_opened", url=url)
            
            return ToolResult(
                success=True,
                tool="open_url",
                message=f"Opened {url} in browser",
                data={"url": url}
            )
            
        except Exception as e:
            logger.error("url_open_error", url=url, error=str(e))
            return ToolResult(
                success=False,
                tool="open_url",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )


application_tools = ApplicationTools()
