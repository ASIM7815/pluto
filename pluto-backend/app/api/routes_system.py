"""System information routes"""
from fastapi import APIRouter
from app.schemas.system import SystemMetrics, SystemInfo
from app.tools.system import system_tools

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics():
    """Get current system metrics"""
    return await system_tools.get_system_metrics()


@router.get("/info")
async def get_info():
    """Get system information"""
    return await system_tools.get_system_info()


@router.get("/status")
async def get_status():
    """Health check endpoint"""
    return {
        "status": "online",
        "agent": "PLUTO v1.0.0",
        "backend": "operational"
    }
