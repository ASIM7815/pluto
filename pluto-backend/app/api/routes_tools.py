"""Tool introspection routes."""
from fastapi import APIRouter

from app.agent.tool_registry import tool_registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools() -> dict:
    """List all registered tools and their permission levels."""
    return {
        "tools": tool_registry.list_tools(),
        "count": len(tool_registry.tools),
    }


@router.get("/permissions")
async def tool_permissions() -> dict:
    """Return the permissions matrix."""
    return {tool_registry.tools[name]["definition"].name: tool_registry.get_permission_level(name)
            for name in tool_registry.tools}
