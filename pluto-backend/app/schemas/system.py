"""System information schemas"""
from pydantic import BaseModel
from typing import Optional


class SystemMetrics(BaseModel):
    """System metrics (matches frontend)"""
    cpu: int
    ram: int
    storage: int
    gpu: Optional[int] = None
    temp: Optional[int] = None
    networkUp: Optional[str] = None
    networkDown: Optional[str] = None


class SystemInfo(BaseModel):
    """Detailed system information"""
    os: str
    distro: str
    host: str
    uptime: str
    securityStatus: str
    voiceEngine: str
    llmEngine: str


class ProcessInfo(BaseModel):
    """Running process information"""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
