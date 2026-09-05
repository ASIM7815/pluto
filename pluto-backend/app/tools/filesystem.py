"""Filesystem operations tools"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List
from app.core.security import security_validator
from app.core.logging import get_logger
from app.schemas.tools import ToolResult

logger = get_logger(__name__)


class FilesystemTools:
    """Safe filesystem operations"""
    
    @staticmethod
    async def create_file(path: str, content: str = "") -> ToolResult:
        """Create a new file"""
        try:
            # Validate path
            is_valid, error_msg = security_validator.validate_path(path)
            if not is_valid:
                return ToolResult(
                    success=False,
                    tool="create_file",
                    error={"code": "PERMISSION_DENIED", "message": error_msg}
                )
            
            abs_path = Path(os.path.expanduser(path))
            
            # Create parent directories if needed
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            abs_path.write_text(content)
            
            logger.info("file_created", path=str(abs_path))
            
            return ToolResult(
                success=True,
                tool="create_file",
                message=f"File created: {abs_path}",
                data={"path": str(abs_path), "size": len(content)}
            )
            
        except Exception as e:
            logger.error("file_create_error", path=path, error=str(e))
            return ToolResult(
                success=False,
                tool="create_file",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )
    
    @staticmethod
    async def read_file(path: str) -> ToolResult:
        """Read file content"""
        try:
            is_valid, error_msg = security_validator.validate_path(path)
            if not is_valid:
                return ToolResult(
                    success=False,
                    tool="read_file",
                    error={"code": "PERMISSION_DENIED", "message": error_msg}
                )
            
            abs_path = Path(os.path.expanduser(path))
            
            if not abs_path.exists():
                return ToolResult(
                    success=False,
                    tool="read_file",
                    error={"code": "FILE_NOT_FOUND", "message": f"File not found: {abs_path}"}
                )
            
            content = abs_path.read_text()
            
            return ToolResult(
                success=True,
                tool="read_file",
                message=f"File read: {abs_path}",
                data={"path": str(abs_path), "content": content, "size": len(content)}
            )
            
        except Exception as e:
            logger.error("file_read_error", path=path, error=str(e))
            return ToolResult(
                success=False,
                tool="read_file",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )
    
    @staticmethod
    async def list_directory(path: str) -> ToolResult:
        """List directory contents"""
        try:
            is_valid, error_msg = security_validator.validate_path(path)
            if not is_valid:
                return ToolResult(
                    success=False,
                    tool="list_directory",
                    error={"code": "PERMISSION_DENIED", "message": error_msg}
                )
            
            abs_path = Path(os.path.expanduser(path))
            
            if not abs_path.exists():
                return ToolResult(
                    success=False,
                    tool="list_directory",
                    error={"code": "DIR_NOT_FOUND", "message": f"Directory not found: {abs_path}"}
                )
            
            items = []
            for item in abs_path.iterdir():
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0
                })
            
            return ToolResult(
                success=True,
                tool="list_directory",
                message=f"Listed {len(items)} items in {abs_path}",
                data={"path": str(abs_path), "items": items}
            )
            
        except Exception as e:
            logger.error("dir_list_error", path=path, error=str(e))
            return ToolResult(
                success=False,
                tool="list_directory",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )
    
    @staticmethod
    async def create_directory(path: str) -> ToolResult:
        """Create directory"""
        try:
            is_valid, error_msg = security_validator.validate_path(path)
            if not is_valid:
                return ToolResult(
                    success=False,
                    tool="create_directory",
                    error={"code": "PERMISSION_DENIED", "message": error_msg}
                )
            
            abs_path = Path(os.path.expanduser(path))
            abs_path.mkdir(parents=True, exist_ok=True)
            
            logger.info("directory_created", path=str(abs_path))
            
            return ToolResult(
                success=True,
                tool="create_directory",
                message=f"Directory created: {abs_path}",
                data={"path": str(abs_path)}
            )
            
        except Exception as e:
            logger.error("dir_create_error", path=path, error=str(e))
            return ToolResult(
                success=False,
                tool="create_directory",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )
    
    @staticmethod
    async def delete_file(path: str) -> ToolResult:
        """Delete file (requires confirmation)"""
        try:
            is_valid, error_msg = security_validator.validate_path(path)
            if not is_valid:
                return ToolResult(
                    success=False,
                    tool="delete_file",
                    error={"code": "PERMISSION_DENIED", "message": error_msg}
                )
            
            abs_path = Path(os.path.expanduser(path))
            
            if not abs_path.exists():
                return ToolResult(
                    success=False,
                    tool="delete_file",
                    error={"code": "FILE_NOT_FOUND", "message": f"File not found: {abs_path}"}
                )
            
            if abs_path.is_dir():
                shutil.rmtree(abs_path)
            else:
                abs_path.unlink()
            
            logger.info("file_deleted", path=str(abs_path))
            
            return ToolResult(
                success=True,
                tool="delete_file",
                message=f"Deleted: {abs_path}",
                data={"path": str(abs_path)}
            )
            
        except Exception as e:
            logger.error("file_delete_error", path=path, error=str(e))
            return ToolResult(
                success=False,
                tool="delete_file",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )


filesystem_tools = FilesystemTools()
