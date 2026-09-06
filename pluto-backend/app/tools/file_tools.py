"""File Management Tools - Open, find, manage files using terminal commands"""
import shlex
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from app.tools.terminal_base import TerminalTool, ToolResult, SafetyLevel, VerificationMixin
from app.core.logging import get_logger

logger = get_logger(__name__)


# Safe base directories
SAFE_DIRECTORIES = [
    "~/Desktop",
    "~/Documents",
    "~/Downloads",
    "~/Pictures",
    "~/Videos",
    "~/Music",
    "~/Projects",
]

# Blocked directories
BLOCKED_DIRECTORIES = [
    "/etc",
    "/sys",
    "/proc",
    "/boot",
    "~/.ssh",
    "/root",
]


class OpenFileTool(TerminalTool, VerificationMixin):
    """Open a file with default application"""
    
    name = "open_file"
    description = "Opens a file with its default application. Works for documents, images, videos, etc."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Full path to the file to open"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        """
        Open a file
        
        Args:
            path: File path
            
        Returns:
            ToolResult
        """
        # Expand home directory
        expanded_path = os.path.expanduser(path)
        
        # Check if file exists
        file_exists = await self.file_exists(expanded_path)
        if not file_exists:
            return ToolResult(
                success=False,
                message=f"File not found: {path}",
                error="File does not exist"
            )
        
        # Check if it's a file (not directory)
        is_file = await self.is_file(expanded_path)
        if not is_file:
            return ToolResult(
                success=False,
                message=f"Path is not a file: {path}",
                error="Not a file"
            )
        
        # Open with xdg-open (opens with default app)
        result = await self.run_command(
            ["xdg-open", expanded_path],
            check_exit_code=False
        )
        
        logger.info("file_opened", path=path, success=result.success)
        return ToolResult(
            success=True,
            message=f"Opened {os.path.basename(path)}",
            output=result.output,
            data={"path": expanded_path, "filename": os.path.basename(path)},
            context_updates={"recent_files": [expanded_path]}
        )


class OpenFolderTool(TerminalTool, VerificationMixin):
    """Open a folder in file manager"""
    
    name = "open_folder"
    description = "Opens a folder/directory in the file manager. Use to browse directories."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Full path to the folder to open"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        """
        Open a folder
        
        Args:
            path: Folder path
            
        Returns:
            ToolResult
        """
        # Expand home directory
        expanded_path = os.path.expanduser(path)
        
        # Check if directory exists
        dir_exists = await self.file_exists(expanded_path)
        if not dir_exists:
            return ToolResult(
                success=False,
                message=f"Folder not found: {path}",
                error="Directory does not exist"
            )
        
        # Check if it's a directory
        is_dir = await self.is_directory(expanded_path)
        if not is_dir:
            return ToolResult(
                success=False,
                message=f"Path is not a folder: {path}",
                error="Not a directory"
            )
        
        # Open with xdg-open (opens in file manager)
        result = await self.run_command(
            ["xdg-open", expanded_path],
            check_exit_code=False
        )
        
        # Verify file manager window opened
        import asyncio
        await asyncio.sleep(1)
        window_exists = await self.verify_window_exists("File", timeout=3)
        
        logger.info("folder_opened", path=path, window_found=window_exists)
        return ToolResult(
            success=True,
            message=f"Opened folder {os.path.basename(path) or path}",
            output=result.output,
            verification_passed=window_exists,
            data={"path": expanded_path, "folder_name": os.path.basename(path)},
            context_updates={"current_directory": expanded_path}
        )


class FindFilesTool(TerminalTool):
    """Find files by name or pattern"""
    
    name = "find_files"
    description = "Searches for files by name pattern. Returns list of matching files."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (filename pattern)"
                },
                "location": {
                    "type": "string",
                    "description": "Where to search (e.g., '~/Documents', '~/Downloads'). Defaults to home directory.",
                    "default": "~"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    
    async def execute(
        self,
        query: str,
        location: str = "~",
        max_results: int = 20,
        **kwargs
    ) -> ToolResult:
        """
        Find files matching query
        
        Args:
            query: Search pattern
            location: Where to search
            max_results: Max results
            
        Returns:
            ToolResult with file list
        """
        # Expand location path
        search_path = os.path.expanduser(location)
        
        # Validate location exists
        path_exists = await self.file_exists(search_path)
        if not path_exists:
            return ToolResult(
                success=False,
                message=f"Search location not found: {location}",
                error="Location does not exist"
            )
        
        # Build find command
        # Use -iname for case-insensitive search
        find_cmd = f"find {shlex.quote(search_path)} -type f -iname '*{query}*' 2>/dev/null | head -n {max_results}"
        
        result = await self.run_command(
            find_cmd,
            shell=True,
            check_exit_code=False
        )
        
        # Parse results
        files = []
        if result.output:
            for line in result.output.strip().split('\n'):
                if line:
                    files.append({
                        "path": line,
                        "name": os.path.basename(line),
                        "directory": os.path.dirname(line)
                    })
        
        logger.info("files_found", query=query, location=location, count=len(files))
        
        # Format message
        if files:
            file_list = "\n".join([f"- {f['name']} ({f['directory']})" for f in files[:10]])
            message = f"Found {len(files)} file(s) matching '{query}':\n{file_list}"
            if len(files) > 10:
                message += f"\n... and {len(files) - 10} more"
        else:
            message = f"No files found matching '{query}' in {location}"
        
        return ToolResult(
            success=True,
            message=message,
            output=result.output,
            data={
                "files": files,
                "count": len(files),
                "query": query,
                "location": location
            },
            context_updates={
                "search_results": files,
                "last_search_query": query
            }
        )


class CreateFolderTool(TerminalTool, VerificationMixin):
    """Create a new folder"""
    
    name = "create_folder"
    description = "Creates a new folder/directory. Use for organizing files or starting projects."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Full path for the new folder"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Create parent directories if needed",
                    "default": True
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, parents: bool = True, **kwargs) -> ToolResult:
        """
        Create a folder
        
        Args:
            path: Folder path
            parents: Create parent dirs
            
        Returns:
            ToolResult
        """
        # Expand path
        expanded_path = os.path.expanduser(path)
        
        # Check if already exists
        already_exists = await self.file_exists(expanded_path)
        if already_exists:
            return ToolResult(
                success=True,
                message=f"Folder already exists: {path}",
                data={"path": expanded_path, "already_existed": True}
            )
        
        # Create directory
        mkdir_cmd = ["mkdir"]
        if parents:
            mkdir_cmd.append("-p")
        mkdir_cmd.append(expanded_path)
        
        result = await self.run_command(mkdir_cmd)
        
        if result.success:
            # Verify creation
            created = await self.file_exists(expanded_path)
            logger.info("folder_created", path=path, verified=created)
            
            return ToolResult(
                success=True,
                message=f"Created folder {os.path.basename(path)}",
                output=result.output,
                verification_passed=created,
                data={"path": expanded_path, "name": os.path.basename(path)}
            )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to create folder: {path}",
                error=result.error
            )


class MoveFileTool(TerminalTool, VerificationMixin):
    """Move or rename a file"""
    
    name = "move_file"
    description = "Moves a file to a new location or renames it. Requires confirmation."
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file path"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path"
                }
            },
            "required": ["source", "destination"]
        }
    
    async def execute(self, source: str, destination: str, **kwargs) -> ToolResult:
        """
        Move/rename file
        
        Args:
            source: Source path
            destination: Destination path
            
        Returns:
            ToolResult
        """
        # Expand paths
        src_path = os.path.expanduser(source)
        dest_path = os.path.expanduser(destination)
        
        # Check source exists
        src_exists = await self.file_exists(src_path)
        if not src_exists:
            return ToolResult(
                success=False,
                message=f"Source file not found: {source}",
                error="Source does not exist"
            )
        
        # Move file
        result = await self.run_command(
            ["mv", src_path, dest_path]
        )
        
        if result.success:
            # Verify move
            dest_exists = await self.file_exists(dest_path)
            src_gone = not await self.file_exists(src_path)
            
            logger.info("file_moved", source=source, destination=destination)
            return ToolResult(
                success=True,
                message=f"Moved {os.path.basename(source)} to {destination}",
                output=result.output,
                verification_passed=(dest_exists and src_gone),
                data={"source": src_path, "destination": dest_path}
            )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to move file: {result.error}",
                error=result.error
            )


class CopyFileTool(TerminalTool, VerificationMixin):
    """Copy a file"""
    
    name = "copy_file"
    description = "Copies a file to a new location. Original file is kept."
    safety_level = SafetyLevel.SAFE
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file path"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path"
                }
            },
            "required": ["source", "destination"]
        }
    
    async def execute(self, source: str, destination: str, **kwargs) -> ToolResult:
        """
        Copy file
        
        Args:
            source: Source path
            destination: Destination path
            
        Returns:
            ToolResult
        """
        # Expand paths
        src_path = os.path.expanduser(source)
        dest_path = os.path.expanduser(destination)
        
        # Check source exists
        src_exists = await self.file_exists(src_path)
        if not src_exists:
            return ToolResult(
                success=False,
                message=f"Source file not found: {source}",
                error="Source does not exist"
            )
        
        # Copy file
        result = await self.run_command(
            ["cp", "-r", src_path, dest_path]  # -r for directories too
        )
        
        if result.success:
            # Verify copy
            dest_exists = await self.file_exists(dest_path)
            
            logger.info("file_copied", source=source, destination=destination)
            return ToolResult(
                success=True,
                message=f"Copied {os.path.basename(source)} to {destination}",
                output=result.output,
                verification_passed=dest_exists,
                data={"source": src_path, "destination": dest_path}
            )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to copy file: {result.error}",
                error=result.error
            )


# Register all tools
FILE_TOOLS = [
    OpenFileTool(),
    OpenFolderTool(),
    FindFilesTool(),
    CreateFolderTool(),
    MoveFileTool(),
    CopyFileTool(),
]
