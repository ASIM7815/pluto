"""System information routes (read-only, real metrics)."""
from fastapi import APIRouter

from app.schemas.system import SystemMetrics, SystemInfo
from app.tools.system_tools import collect_system_metrics, collect_system_info

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics() -> dict:
    """Get current system metrics."""
    return await collect_system_metrics()


@router.get("/info", response_model=SystemInfo)
async def get_info() -> dict:
    """Get system information."""
    return await collect_system_info()


@router.get("/status")
async def get_status() -> dict:
    """Health status endpoint."""
    return {"status": "online", "agent": "PLUTO v1.0.0", "backend": "operational"}
