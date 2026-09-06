"""Terminal Tool Base - Foundation for terminal-based tool execution"""
import subprocess
import shlex
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
from app.core.logging import get_logger

logger = get_logger(__name__)


class SafetyLevel(str, Enum):
    """Tool safety classification"""
    SAFE = "safe"                    # Auto-execute, no confirmation needed
    CONFIRM_REQUIRED = "confirm"     # Ask user before executing
    DANGEROUS = "dangerous"          # Blocked by default, explicit permission required


@dataclass
class ToolResult:
    """Result of tool execution"""
    success: bool
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    verification_passed: bool = True
    context_updates: Optional[Dict[str, Any]] = None


class TerminalTool:
    """
    Base class for terminal-based tools
    
    All PLUTO tools that use terminal commands should inherit from this.
    Provides command execution, verification, and safety features.
    """
    
    # Tool metadata (override in subclasses)
    name: str = "base_tool"
    description: str = "Base terminal tool"
    safety_level: SafetyLevel = SafetyLevel.SAFE
    
    # Command execution settings
    timeout: int = 30  # seconds
    shell: bool = False  # Whether to use shell=True
    
    def __init__(self):
        self.logger = logger
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool (override in subclasses)
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with execution outcome
        """
        raise NotImplementedError("Subclasses must implement execute()")
    
    async def verify(self, result: ToolResult, **kwargs) -> bool:
        """
        Verify that the tool execution succeeded (override in subclasses)
        
        Args:
            result: The ToolResult from execution
            **kwargs: Original parameters for verification
            
        Returns:
            True if verification passed, False otherwise
        """
        # Default: trust the exit code
        return result.success
    
    async def run_command(
        self,
        command: Union[str, List[str]],
        shell: bool = False,
        timeout: Optional[int] = None,
        check_exit_code: bool = True,
        env: Optional[Dict[str, str]] = None
    ) -> ToolResult:
        """
        Execute a terminal command
        
        Args:
            command: Command string or list of command parts
            shell: Whether to use shell execution
            timeout: Command timeout in seconds
            check_exit_code: Whether to check exit code for success
            env: Environment variables
            
        Returns:
            ToolResult with command output
        """
        timeout = timeout or self.timeout
        
        try:
            # Prepare command
            if isinstance(command, str) and not shell:
                # Split command safely
                command_parts = shlex.split(command)
            else:
                command_parts = command
            
            self.logger.debug(
                "terminal_command_start",
                tool=self.name,
                command=command if isinstance(command, str) else " ".join(command)
            )
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *command_parts if not shell else [command],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                shell=shell
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    message=f"Command timed out after {timeout} seconds",
                    error=f"Timeout: {timeout}s",
                    exit_code=-1
                )
            
            # Decode output
            stdout_text = stdout.decode('utf-8', errors='replace').strip()
            stderr_text = stderr.decode('utf-8', errors='replace').strip()
            
            # Determine success
            success = process.returncode == 0 if check_exit_code else True
            
            # Log result
            self.logger.info(
                "terminal_command_complete",
                tool=self.name,
                success=success,
                exit_code=process.returncode,
                output_length=len(stdout_text)
            )
            
            return ToolResult(
                success=success,
                message=stdout_text or stderr_text or "Command executed",
                output=stdout_text,
                error=stderr_text if not success else None,
                exit_code=process.returncode
            )
            
        except FileNotFoundError:
            return ToolResult(
                success=False,
                message=f"Command not found: {command_parts[0] if isinstance(command_parts, list) else command}",
                error="Command not found",
                exit_code=-1
            )
        except Exception as e:
            self.logger.error("terminal_command_error", tool=self.name, error=str(e))
            return ToolResult(
                success=False,
                message=f"Error executing command: {str(e)}",
                error=str(e),
                exit_code=-1
            )
    
    async def check_command_exists(self, command: str) -> bool:
        """
        Check if a command exists on the system
        
        Args:
            command: Command name to check
            
        Returns:
            True if command exists, False otherwise
        """
        result = await self.run_command(
            f"which {command}",
            check_exit_code=True
        )
        return result.success
    
    async def check_process_running(self, process_name: str) -> bool:
        """
        Check if a process is running
        
        Args:
            process_name: Process name to check
            
        Returns:
            True if process is running, False otherwise
        """
        result = await self.run_command(
            f"pgrep -x {process_name}",
            check_exit_code=True
        )
        return result.success
    
    async def get_process_pid(self, process_name: str) -> Optional[int]:
        """
        Get PID of a running process
        
        Args:
            process_name: Process name
            
        Returns:
            PID or None if not running
        """
        result = await self.run_command(
            f"pgrep -x {process_name}",
            check_exit_code=True
        )
        if result.success and result.output:
            try:
                return int(result.output.split('\n')[0])
            except (ValueError, IndexError):
                return None
        return None
    
    async def get_window_title(self) -> Optional[str]:
        """
        Get the title of the currently focused window
        
        Returns:
            Window title or None
        """
        # Try xdotool first
        result = await self.run_command(
            "xdotool getwindowfocus getwindowname",
            check_exit_code=False
        )
        if result.success and result.output:
            return result.output
        
        # Try wmctrl as fallback
        result = await self.run_command(
            "wmctrl -l | grep $(xdotool getwindowfocus | cut -d' ' -f1) | cut -d' ' -f5-",
            shell=True,
            check_exit_code=False
        )
        if result.success and result.output:
            return result.output
        
        return None
    
    async def file_exists(self, path: str) -> bool:
        """
        Check if a file or directory exists
        
        Args:
            path: File/directory path
            
        Returns:
            True if exists, False otherwise
        """
        result = await self.run_command(
            f"test -e {shlex.quote(path)}",
            shell=True,
            check_exit_code=True
        )
        return result.success
    
    async def is_directory(self, path: str) -> bool:
        """
        Check if path is a directory
        
        Args:
            path: Path to check
            
        Returns:
            True if directory, False otherwise
        """
        result = await self.run_command(
            f"test -d {shlex.quote(path)}",
            shell=True,
            check_exit_code=True
        )
        return result.success
    
    async def is_file(self, path: str) -> bool:
        """
        Check if path is a regular file
        
        Args:
            path: Path to check
            
        Returns:
            True if file, False otherwise
        """
        result = await self.run_command(
            f"test -f {shlex.quote(path)}",
            shell=True,
            check_exit_code=True
        )
        return result.success
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get tool schema for GPT-OSS function calling
        
        Returns:
            OpenAI function schema
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters_schema()
        }
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Get parameters schema (override in subclasses)
        
        Returns:
            JSON schema for parameters
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }


class VerificationMixin:
    """Mixin for common verification strategies"""
    
    async def verify_process_started(self, process_name: str, timeout: int = 5) -> bool:
        """
        Verify that a process has started
        
        Args:
            process_name: Process name to check
            timeout: How long to wait for process
            
        Returns:
            True if process is running
        """
        for _ in range(timeout):
            result = await self.run_command(
                f"pgrep -x {process_name}",
                check_exit_code=True
            )
            if result.success:
                return True
            await asyncio.sleep(1)
        return False
    
    async def verify_window_exists(self, window_name: str, timeout: int = 5) -> bool:
        """
        Verify that a window with given name exists
        
        Args:
            window_name: Window name/title substring
            timeout: How long to wait
            
        Returns:
            True if window exists
        """
        for _ in range(timeout):
            result = await self.run_command(
                f"wmctrl -l | grep -i {shlex.quote(window_name)}",
                shell=True,
                check_exit_code=True
            )
            if result.success:
                return True
            await asyncio.sleep(1)
        return False
    
    async def verify_file_created(self, file_path: str, timeout: int = 5) -> bool:
        """
        Verify that a file was created
        
        Args:
            file_path: Path to file
            timeout: How long to wait
            
        Returns:
            True if file exists
        """
        for _ in range(timeout):
            result = await self.run_command(
                f"test -f {shlex.quote(file_path)}",
                shell=True,
                check_exit_code=True
            )
            if result.success:
                return True
            await asyncio.sleep(1)
        return False
