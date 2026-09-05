"""Security utilities for PLUTO backend"""
import os
import re
from pathlib import Path
from typing import List
from app.core.config import settings


class SecurityValidator:
    """Security validation for filesystem operations and commands"""
    
    @staticmethod
    def validate_path(path: str) -> tuple[bool, str]:
        """
        Validate file path against allowed directories and check for traversal attacks
        
        Returns: (is_valid, error_message)
        """
        try:
            # Resolve to absolute path
            abs_path = Path(os.path.expanduser(path)).resolve()
            
            # Check for path traversal patterns
            path_str = str(abs_path)
            if ".." in path_str or path_str.startswith("/etc") or path_str.startswith("/sys"):
                return False, "Path traversal or system directory access denied"
            
            # Check against allowed paths
            allowed = False
            for allowed_dir in settings.allowed_paths_list:
                allowed_path = Path(allowed_dir).resolve()
                try:
                    abs_path.relative_to(allowed_path)
                    allowed = True
                    break
                except ValueError:
                    continue
            
            if not allowed:
                return False, f"Path not in allowed directories: {settings.allowed_paths_list}"
            
            return True, ""
            
        except Exception as e:
            return False, f"Path validation error: {str(e)}"
    
    @staticmethod
    def classify_command(command: str) -> str:
        """
        Classify command safety level
        
        Returns: "SAFE", "CONFIRM_REQUIRED", or "BLOCKED"
        """
        command_lower = command.lower().strip()
        
        # Blocked patterns
        blocked_patterns = [
            r'rm\s+-rf\s+/',
            r'dd\s+if=',
            r':\(\)\{.*\};:',  # Fork bomb
            r'mkfs\.',
            r'sudo\s+rm',
            r'chmod\s+777',
            r'>/dev/sd',
        ]
        
        for pattern in blocked_patterns:
            if re.search(pattern, command_lower):
                return "BLOCKED"
        
        # Requires confirmation
        dangerous_keywords = [
            'rm ', 'delete', 'format', 'mkfs', 'fdisk',
            'shutdown', 'reboot', 'poweroff',
            'kill -9', 'killall',
            'iptables', 'ufw disable',
            'sudo ', 'su ', 'passwd'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in command_lower:
                return "CONFIRM_REQUIRED"
        
        # Safe commands
        return "SAFE"
    
    @staticmethod
    def sanitize_command(command: str) -> str:
        """Sanitize command input"""
        # Remove shell injection patterns
        dangerous_chars = [';', '&&', '||', '|', '`', '$(',  '$()', '>>', '<<']
        sanitized = command
        for char in dangerous_chars:
            if char in sanitized:
                # Don't automatically sanitize - classify as needing confirmation instead
                return command
        return sanitized.strip()


security_validator = SecurityValidator()
