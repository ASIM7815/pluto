"""File Management Tools - real, sandboxed, verified operations.

All paths are expanded and checked against the security sandbox
(PLUTO_ALLOWED_PATHS) before any OS mutation. Every tool verifies its effect
and reports an honest ToolResult - never a fabricated success.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.security import security_validator
from app.core.logging import get_logger
from app.tools.terminal_base import (
    TerminalTool,
    ToolResult,
    SafetyLevel,
    VerificationMixin,
    command_exists,
    has_display,
    human_display_hint,
)

logger = get_logger(__name__)

MAX_FILE_READ_CHARS = 200_000  # cap content fed to the LLM

# Desktop "open with default application" launchers, tried in order.
_OPENERS = ("xdg-open", "gio", "exo-open")


def _opener_command() -> Optional[List[str]]:
    """Return the first installed desktop opener as an argv prefix."""
    for opener in _OPENERS:
        if command_exists(opener):
            return [opener] if opener != "gio" else ["gio", "open"]
    return None


def _resolve_and_check(path: str) -> tuple[Optional[str], Optional[ToolResult]]:
    """Expand + validate a path against the sandbox.

    Returns (abs_path, None) on success, (None, error_result) on failure.
    """
    expanded = os.path.expanduser(path)
    is_valid, message = security_validator.validate_path(expanded)
    if not is_valid:
        return None, ToolResult.fail(
            "file_tool", f"Access denied: {message}", error_code="PERMISSION_DENIED"
        )
    return expanded, None


class OpenFileTool(TerminalTool, VerificationMixin):
    """Open a file with its default application."""

    name = "open_file"
    description = (
        "Opens a file with its default desktop application (document, image, "
        "video, etc.). Requires a graphical desktop session."
    )
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full path to the file to open"}
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err

        if not os.path.exists(abs_path):
            return ToolResult.fail(self.name, f"File not found: {path}", error_code="FILE_NOT_FOUND")
        if os.path.isdir(abs_path):
            return ToolResult.fail(self.name, f"Path is a folder, not a file: {path}", error_code="NOT_A_FILE")

        opener = _opener_command()
        if opener is None:
            return ToolResult.fail(
                self.name,
                "No desktop opener is installed (tried xdg-open, gio, exo-open), "
                "so files cannot be opened with a default application.",
                error_code="MISSING_DEPENDENCY",
            )
        if not has_display():
            return ToolResult.fail(
                self.name, human_display_hint(), error_code="NO_DISPLAY"
            )

        result = await self.run_command(opener + [abs_path], check_exit_code=False)
        if not result.success:
            return ToolResult.fail(
                self.name,
                f"Could not open {os.path.basename(path)} with its default application.",
                error=result.error, error_code="OPEN_FAILED",
            )
        return ToolResult.ok(
            self.name,
            message=f"Opened {os.path.basename(path)} in its default application.",
            data={"path": abs_path, "filename": os.path.basename(path)},
            context_updates={"recent_files": [abs_path], "current_directory": os.path.dirname(abs_path)},
            verification_passed=True,
        )


class OpenFolderTool(TerminalTool, VerificationMixin):
    """Open a folder in the file manager."""

    name = "open_folder"
    description = "Opens a folder/directory in the graphical file manager."
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full path to the folder to open"}
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err
        if not os.path.isdir(abs_path):
            return ToolResult.fail(self.name, f"Folder not found: {path}", error_code="DIR_NOT_FOUND")
        opener = _opener_command()
        if opener is None:
            return ToolResult.fail(
                self.name,
                "No desktop opener is installed (tried xdg-open, gio, exo-open).",
                error_code="MISSING_DEPENDENCY",
            )
        if not has_display():
            return ToolResult.fail(self.name, human_display_hint(), error_code="NO_DISPLAY")

        result = await self.run_command(opener + [abs_path], check_exit_code=False)
        if not result.success:
            return ToolResult.fail(
                self.name,
                f"Could not open folder {path}: {result.error or 'opener failed'}",
                error_code="OPEN_FAILED",
            )
        return ToolResult.ok(
            self.name,
            message=f"Opened folder {os.path.basename(abs_path) or abs_path} in the file manager.",
            data={"path": abs_path},
            context_updates={"current_directory": abs_path},
            verification_passed=True,
        )


class FindFilesTool(TerminalTool):
    """Find files by name (bounded walk, respects the sandbox)."""

    name = "find_files"
    description = (
        "Searches for files by name pattern inside an allowed directory "
        "and returns the matching paths (max 25)."
    )
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Filename substring to search for"},
                "location": {
                    "type": "string",
                    "description": "Directory to search (default: ~, i.e. home)",
                    "default": "~",
                },
                "max_results": {"type": "integer", "default": 25},
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        location: str = "~",
        max_results: int = 25,
        **kwargs,
    ) -> ToolResult:
        search_dir, err = _resolve_and_check(location or "~")
        if err:
            return err
        if not os.path.isdir(search_dir):
            return ToolResult.fail(
                self.name, f"Search location not found: {location}", error_code="DIR_NOT_FOUND"
            )

        max_results = max(1, min(int(max_results or 25), 100))
        query_lower = (query or "").lower()
        matches: List[Dict[str, Any]] = []

        for root, dirs, files in os.walk(search_dir):
            # Skip hidden dirs and common noise.
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", ".git", "__pycache__")]
            for name in files:
                if query_lower in name.lower():
                    full = os.path.join(root, name)
                    matches.append({
                        "path": full,
                        "name": name,
                        "directory": root,
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        if not matches:
            return ToolResult.ok(
                self.name,
                message=f"No files found matching '{query}' in {location}.",
                data={"files": [], "count": 0, "query": query, "location": location},
            )
        names = "\n".join(f"- {m['path']}" for m in matches[:10])
        more = f"\n... and {len(matches) - 10} more" if len(matches) > 10 else ""
        return ToolResult.ok(
            self.name,
            message=f"Found {len(matches)} file(s) matching '{query}':\n{names}{more}",
            data={"files": matches, "count": len(matches), "query": query, "location": location},
            context_updates={"last_search_query": query, "search_results": matches},
        )


class CreateFolderTool(TerminalTool, VerificationMixin):
    """Create a new folder."""

    name = "create_folder"
    description = "Creates a new folder/directory (with parent directories if needed)."
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full path for the new folder"},
                "parents": {"type": "boolean", "description": "Create parents if needed", "default": True},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, parents: bool = True, **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err
        if os.path.exists(abs_path):
            return ToolResult.ok(
                self.name,
                message=f"Folder already exists: {abs_path}",
                data={"path": abs_path, "already_existed": True},
                context_updates={"current_directory": abs_path},
            )
        try:
            if parents:
                os.makedirs(abs_path, exist_ok=True)
            else:
                os.mkdir(abs_path)
        except OSError as e:
            logger.error("folder_create_error", path=path, error=str(e))
            return ToolResult.fail(
                self.name, f"Failed to create folder: {e}", error_code="CREATE_FAILED"
            )

        created = os.path.isdir(abs_path)
        return ToolResult.ok(
            self.name,
            message=f"Created folder {abs_path}",
            data={"path": abs_path, "name": os.path.basename(abs_path)},
            verification_passed=created,
            context_updates={"current_directory": abs_path},
        )


class CreateFileTool(TerminalTool, VerificationMixin):
    """Create a new file with content."""

    name = "create_file"
    description = "Creates a new text file at the given path, optionally with content."
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full path for the new file"},
                "content": {"type": "string", "description": "File content (optional)"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, content: str = "", **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err
        try:
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as fh:
                fh.write(content or "")
        except OSError as e:
            logger.error("file_create_error", path=path, error=str(e))
            return ToolResult.fail(
                self.name, f"Failed to create file: {e}", error_code="CREATE_FAILED"
            )
        exists = os.path.isfile(abs_path)
        return ToolResult.ok(
            self.name,
            message=f"Created file {abs_path}",
            data={"path": abs_path, "size": len(content or "")},
            verification_passed=exists,
            context_updates={"recent_files": [abs_path]},
        )


class ReadFileTool(TerminalTool):
    """Read file content."""

    name = "read_file"
    description = "Reads the content of a text file (content is truncated to keep context small)."
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Full path of the file to read"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err
        if not os.path.isfile(abs_path):
            return ToolResult.fail(self.name, f"File not found: {path}", error_code="FILE_NOT_FOUND")
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read(MAX_FILE_READ_CHARS)
        except OSError as e:
            return ToolResult.fail(self.name, f"Could not read file: {e}", error_code="READ_FAILED")
        truncated = len(content) >= MAX_FILE_READ_CHARS
        return ToolResult.ok(
            self.name,
            message=f"Read {os.path.basename(abs_path)} ({len(content)} chars)"
            + (" - truncated" if truncated else ""),
            data={"path": abs_path, "content": content, "truncated": truncated},
            context_updates={"recent_files": [abs_path]},
        )


class ListDirectoryTool(TerminalTool):
    """List directory contents."""

    name = "list_directory"
    description = "Lists the entries of a directory (names, types, sizes)."
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"],
        }

    async def execute(self, path: str = "~", **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err
        if not os.path.isdir(abs_path):
            return ToolResult.fail(self.name, f"Directory not found: {path}", error_code="DIR_NOT_FOUND")
        items = []
        try:
            for entry in sorted(os.scandir(abs_path), key=lambda e: e.name.lower()):
                try:
                    is_dir = entry.is_dir()
                    size = entry.stat().st_size if not is_dir else 0
                except OSError:
                    is_dir, size = False, 0
                items.append({"name": entry.name, "path": entry.path, "type": "directory" if is_dir else "file", "size": size})
        except OSError as e:
            return ToolResult.fail(self.name, f"Could not list directory: {e}", error_code="LIST_FAILED")
        return ToolResult.ok(
            self.name,
            message=f"Listed {len(items)} item(s) in {abs_path}",
            data={"path": abs_path, "items": items[:500]},
            context_updates={"current_directory": abs_path},
        )


class DeleteFileTool(TerminalTool, VerificationMixin):
    """Delete a file or directory (confirmation required upstream)."""

    name = "delete_file"
    description = "Permanently deletes a file or directory. Requires user confirmation."
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File/directory path to delete"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs) -> ToolResult:
        abs_path, err = _resolve_and_check(path)
        if err:
            return err
        if not os.path.exists(abs_path):
            return ToolResult.fail(self.name, f"Path not found: {path}", error_code="FILE_NOT_FOUND")

        # Refuse deleting sandbox roots themselves.
        from app.core.config import settings
        for allowed in settings.allowed_paths_list:
            if abs_path.rstrip("/") == os.path.expanduser(allowed).rstrip("/"):
                return ToolResult.fail(
                    self.name, "Refusing to delete an allowed root directory.",
                    error_code="PERMISSION_DENIED",
                )

        try:
            if os.path.isdir(abs_path):
                import shutil
                shutil.rmtree(abs_path)
            else:
                os.unlink(abs_path)
        except OSError as e:
            return ToolResult.fail(self.name, f"Delete failed: {e}", error_code="DELETE_FAILED")

        gone = not os.path.exists(abs_path)
        return ToolResult.ok(
            self.name,
            message=f"Deleted {abs_path}",
            data={"path": abs_path},
            verification_passed=gone,
        )


class MoveFileTool(TerminalTool, VerificationMixin):
    """Move or rename a file (confirmation required upstream)."""

    name = "move_file"
    description = "Moves a file/folder to a new location or renames it. Requires confirmation."
    safety_level = SafetyLevel.CONFIRM_REQUIRED
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "destination"],
        }

    async def execute(self, source: str, destination: str, **kwargs) -> ToolResult:
        src, err = _resolve_and_check(source)
        if err:
            return err
        dest, err = _resolve_and_check(destination)
        if err:
            return err
        if not os.path.exists(src):
            return ToolResult.fail(self.name, f"Source not found: {source}", error_code="FILE_NOT_FOUND")
        try:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            os.replace(src, dest)
        except OSError as e:
            return ToolResult.fail(self.name, f"Move failed: {e}", error_code="MOVE_FAILED")
        return ToolResult.ok(
            self.name,
            message=f"Moved {os.path.basename(source)} to {destination}",
            data={"source": src, "destination": dest},
            verification_passed=os.path.exists(dest) and not os.path.exists(src),
            context_updates={"recent_files": [dest]},
        )


class CopyFileTool(TerminalTool, VerificationMixin):
    """Copy a file/folder (keeps the original)."""

    name = "copy_file"
    description = "Copies a file or folder to a new location. The original is kept."
    safety_level = SafetyLevel.SAFE
    category = "file"

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "destination"],
        }

    async def execute(self, source: str, destination: str, **kwargs) -> ToolResult:
        src, err = _resolve_and_check(source)
        if err:
            return err
        dest, err = _resolve_and_check(destination)
        if err:
            return err
        if not os.path.exists(src):
            return ToolResult.fail(self.name, f"Source not found: {source}", error_code="FILE_NOT_FOUND")
        try:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            if os.path.isdir(src):
                import shutil
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                import shutil
                shutil.copy2(src, dest)
        except OSError as e:
            return ToolResult.fail(self.name, f"Copy failed: {e}", error_code="COPY_FAILED")
        return ToolResult.ok(
            self.name,
            message=f"Copied {os.path.basename(source)} to {destination}",
            data={"source": src, "destination": dest},
            verification_passed=os.path.exists(dest),
            context_updates={"recent_files": [dest]},
        )


# Registered tools
FILE_TOOLS: List[TerminalTool] = [
    OpenFileTool(),
    OpenFolderTool(),
    FindFilesTool(),
    CreateFolderTool(),
    CreateFileTool(),
    ReadFileTool(),
    ListDirectoryTool(),
    DeleteFileTool(),
    MoveFileTool(),
    CopyFileTool(),
]
