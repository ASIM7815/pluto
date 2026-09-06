"""System Control Tools - Screenshot, volume, clipboard using terminal commands"""
import shlex
import os
from datetime import datetime
from typing import Optional, Dict, Any
from app.tools.terminal_base import TerminalTool, ToolResult, SafetyLevel, VerificationMixin
from app.core.logging import get_logger

logger = get_logger(__name__)


class TakeScreenshotTool(TerminalTool, VerificationMixin):
    """Take a screenshot"""
    
    name = "take_screenshot"
    description = "Takes a screenshot of the entire screen or a specific area. Saves to Pictures folder."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Custom filename (optional). Auto-generated if not provided.",
                },
                "area": {
                    "type": "string",
                    "description": "Screenshot area: 'full' (entire screen), 'select' (user selects area), or 'window' (active window)",
                    "enum": ["full", "select", "window"],
                    "default": "full"
                }
            },
            "required": []
        }
    
    async def execute(
        self,
        filename: Optional[str] = None,
        area: str = "full",
        **kwargs
    ) -> ToolResult:
        """
        Take a screenshot
        
        Args:
            filename: Custom filename (optional)
            area: Screenshot area type
            
        Returns:
            ToolResult with screenshot path
        """
        # Check if scrot is installed
        has_scrot = await self.check_command_exists("scrot")
        
        if not has_scrot:
            return ToolResult(
                success=False,
                message="Screenshot tool (scrot) not installed. Install with: sudo apt install scrot",
                error="scrot command not found"
            )
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
        
        # Ensure .png extension
        if not filename.endswith('.png'):
            filename += '.png'
        
        # Save to Pictures folder
        pictures_dir = os.path.expanduser("~/Pictures")
        screenshot_path = os.path.join(pictures_dir, filename)
        
        # Ensure Pictures directory exists
        await self.run_command(["mkdir", "-p", pictures_dir])
        
        # Build scrot command based on area
        scrot_cmd = ["scrot"]
        
        if area == "select":
            # User selects area with mouse
            scrot_cmd.extend(["-s", "-f"])  # -s: select area, -f: freeze screen
        elif area == "window":
            # Active window only
            scrot_cmd.extend(["-u"])  # -u: currently focused window
        # else: full screen (default, no flags needed)
        
        scrot_cmd.append(screenshot_path)
        
        # Take screenshot
        result = await self.run_command(scrot_cmd, timeout=15)  # Allow time for selection
        
        if result.success:
            # Verify file was created
            file_exists = await self.verify_file_created(screenshot_path, timeout=2)
            
            if file_exists:
                logger.info("screenshot_taken", path=screenshot_path, area=area)
                return ToolResult(
                    success=True,
                    message=f"Screenshot saved to {filename}",
                    output=screenshot_path,
                    verification_passed=True,
                    data={
                        "path": screenshot_path,
                        "filename": filename,
                        "area": area
                    },
                    context_updates={"last_screenshot": screenshot_path}
                )
            else:
                return ToolResult(
                    success=False,
                    message="Screenshot command ran but file was not created",
                    error="File not found after screenshot",
                    verification_passed=False
                )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to take screenshot: {result.error}",
                error=result.error
            )


class SetVolumeTool(TerminalTool):
    """Set system volume"""
    
    name = "set_volume"
    description = "Sets the system audio volume. Use percentage (0-100) or keywords like 'mute', 'unmute'."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "description": "Volume level: number 0-100, or 'mute', 'unmute'"
                }
            },
            "required": ["level"]
        }
    
    async def execute(self, level: str, **kwargs) -> ToolResult:
        """
        Set volume
        
        Args:
            level: Volume level or command
            
        Returns:
            ToolResult
        """
        # Check if pactl is available
        has_pactl = await self.check_command_exists("pactl")
        
        if not has_pactl:
            return ToolResult(
                success=False,
                message="Volume control (pactl/pulseaudio) not available. Install with: sudo apt install pulseaudio-utils",
                error="pactl command not found"
            )
        
        level_lower = level.lower().strip()
        
        # Handle mute/unmute
        if level_lower == "mute":
            result = await self.run_command(
                "pactl set-sink-mute @DEFAULT_SINK@ 1",
                shell=True
            )
            if result.success:
                logger.info("volume_muted")
                return ToolResult(
                    success=True,
                    message="Audio muted",
                    context_updates={"volume_muted": True}
                )
        
        elif level_lower == "unmute":
            result = await self.run_command(
                "pactl set-sink-mute @DEFAULT_SINK@ 0",
                shell=True
            )
            if result.success:
                logger.info("volume_unmuted")
                return ToolResult(
                    success=True,
                    message="Audio unmuted",
                    context_updates={"volume_muted": False}
                )
        
        else:
            # Set volume percentage
            try:
                volume_int = int(level_lower.rstrip('%'))
                if volume_int < 0 or volume_int > 100:
                    return ToolResult(
                        success=False,
                        message="Volume must be between 0 and 100",
                        error="Invalid volume range"
                    )
                
                result = await self.run_command(
                    f"pactl set-sink-volume @DEFAULT_SINK@ {volume_int}%",
                    shell=True
                )
                
                if result.success:
                    logger.info("volume_set", level=volume_int)
                    return ToolResult(
                        success=True,
                        message=f"Volume set to {volume_int}%",
                        context_updates={"volume_level": volume_int}
                    )
            except ValueError:
                return ToolResult(
                    success=False,
                    message=f"Invalid volume level: {level}. Use 0-100 or 'mute'/'unmute'",
                    error="Invalid volume format"
                )
        
        return ToolResult(
            success=False,
            message=f"Failed to set volume: {result.error if 'result' in locals() else 'Unknown error'}",
            error="Volume command failed"
        )


class GetVolumeTool(TerminalTool):
    """Get current system volume"""
    
    name = "get_volume"
    description = "Gets the current system audio volume level."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        Get current volume
        
        Returns:
            ToolResult with volume info
        """
        # Get volume using pactl
        result = await self.run_command(
            "pactl get-sink-volume @DEFAULT_SINK@ | grep -Po '\\d+(?=%)' | head -1",
            shell=True,
            check_exit_code=False
        )
        
        if result.success and result.output:
            try:
                volume = int(result.output.strip())
                logger.info("volume_retrieved", level=volume)
                return ToolResult(
                    success=True,
                    message=f"Current volume: {volume}%",
                    output=str(volume),
                    data={"volume": volume}
                )
            except ValueError:
                pass
        
        return ToolResult(
            success=False,
            message="Could not retrieve volume",
            error="Failed to parse volume output"
        )


class CopyToClipboardTool(TerminalTool):
    """Copy text to clipboard"""
    
    name = "copy_to_clipboard"
    description = "Copies text to the system clipboard. Use for sharing text between applications."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to copy to clipboard"
                }
            },
            "required": ["text"]
        }
    
    async def execute(self, text: str, **kwargs) -> ToolResult:
        """
        Copy text to clipboard
        
        Args:
            text: Text to copy
            
        Returns:
            ToolResult
        """
        # Check if xclip is installed
        has_xclip = await self.check_command_exists("xclip")
        
        if not has_xclip:
            return ToolResult(
                success=False,
                message="Clipboard tool (xclip) not installed. Install with: sudo apt install xclip",
                error="xclip command not found"
            )
        
        # Copy to clipboard using xclip
        result = await self.run_command(
            f"echo {shlex.quote(text)} | xclip -selection clipboard",
            shell=True
        )
        
        if result.success:
            logger.info("clipboard_copied", length=len(text))
            return ToolResult(
                success=True,
                message=f"Copied {len(text)} characters to clipboard",
                data={"length": len(text), "preview": text[:50]}
            )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to copy to clipboard: {result.error}",
                error=result.error
            )


class GetClipboardTool(TerminalTool):
    """Get text from clipboard"""
    
    name = "get_clipboard"
    description = "Gets text from the system clipboard. Use to retrieve copied content."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        Get clipboard content
        
        Returns:
            ToolResult with clipboard text
        """
        # Check if xclip is installed
        has_xclip = await self.check_command_exists("xclip")
        
        if not has_xclip:
            return ToolResult(
                success=False,
                message="Clipboard tool (xclip) not installed. Install with: sudo apt install xclip",
                error="xclip command not found"
            )
        
        # Get clipboard content
        result = await self.run_command(
            "xclip -selection clipboard -o",
            shell=True,
            check_exit_code=False
        )
        
        if result.success or result.output:
            clipboard_text = result.output or ""
            logger.info("clipboard_retrieved", length=len(clipboard_text))
            return ToolResult(
                success=True,
                message=f"Retrieved {len(clipboard_text)} characters from clipboard",
                output=clipboard_text,
                data={"text": clipboard_text, "length": len(clipboard_text)}
            )
        else:
            return ToolResult(
                success=False,
                message="Clipboard is empty or could not be read",
                error="No clipboard content"
            )


# Register all tools
SYSTEM_TOOLS = [
    TakeScreenshotTool(),
    SetVolumeTool(),
    GetVolumeTool(),
    CopyToClipboardTool(),
    GetClipboardTool(),
]
