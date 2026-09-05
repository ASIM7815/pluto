"""Safe terminal command execution"""
import subprocess
import shlex
from typing import Optional
from app.core.security import security_validator
from app.core.logging import get_logger
from app.schemas.tools import ToolResult

logger = get_logger(__name__)


class TerminalTools:
    """Safe terminal command execution"""
    
    @staticmethod
    async def execute_command(
        command: str,
        working_directory: Optional[str] = None,
        timeout: int = 30
    ) -> ToolResult:
        """
        Execute terminal command with safety checks
        
        Args:
            command: Command to execute
            working_directory: Optional working directory
            timeout: Execution timeout in seconds
        """
        try:
            # Classify command safety
            safety_level = security_validator.classify_command(command)
            
            if safety_level == "BLOCKED":
                return ToolResult(
                    success=False,
                    tool="execute_command",
                    error={
                        "code": "COMMAND_BLOCKED",
                        "message": f"Command blocked for security reasons: {command}"
                    }
                )
            
            # Note: CONFIRM_REQUIRED should be handled by orchestrator before calling this
            
            logger.info("executing_command", command=command, safety=safety_level)
            
            # Execute command safely
            result = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_directory
            )
            
            return ToolResult(
                success=result.returncode == 0,
                tool="execute_command",
                message="Command executed" if result.returncode == 0 else "Command failed",
                data={
                    "command": command,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                tool="execute_command",
                error={
                    "code": "TIMEOUT",
                    "message": f"Command timed out after {timeout} seconds"
                }
            )
        except Exception as e:
            logger.error("command_execution_error", command=command, error=str(e))
            return ToolResult(
                success=False,
                tool="execute_command",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )


terminal_tools = TerminalTools()
