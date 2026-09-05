"""System information and monitoring tools"""
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, Any
from app.schemas.system import SystemMetrics, ProcessInfo
from app.schemas.tools import ToolResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class SystemTools:
    """System monitoring and information"""
    
    @staticmethod
    async def get_system_metrics() -> SystemMetrics:
        """Get current system metrics"""
        try:
            cpu_percent = int(psutil.cpu_percent(interval=0.1))
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # GPU monitoring (basic - would need nvidia-ml-py for real GPU stats)
            gpu_percent = None
            
            # Temperature (if available)
            temp = None
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    temp = int(list(temps.values())[0][0].current)
            except:
                pass
            
            # Network stats
            net = psutil.net_io_counters()
            network_up = f"{net.bytes_sent / (1024**2):.1f} MB"
            network_down = f"{net.bytes_recv / (1024**2):.1f} MB"
            
            return SystemMetrics(
                cpu=cpu_percent,
                ram=int(memory.percent),
                storage=int(disk.percent),
                gpu=gpu_percent,
                temp=temp,
                networkUp=network_up,
                networkDown=network_down
            )
            
        except Exception as e:
            logger.error("system_metrics_error", error=str(e))
            # Return default values
            return SystemMetrics(cpu=0, ram=0, storage=0)
    
    @staticmethod
    async def get_system_info() -> Dict[str, Any]:
        """Get detailed system information"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_seconds = (datetime.now() - boot_time).total_seconds()
            uptime_str = str(timedelta(seconds=int(uptime_seconds)))
            
            return {
                "os": f"{platform.system()} {platform.machine()}",
                "distro": platform.platform(),
                "host": platform.node(),
                "uptime": uptime_str,
                "securityStatus": "Encrypted & Isolated",
                "voiceEngine": "PLUTO ElevenLabs TTS",
                "llmEngine": "GPT-OSS (Groq Llama 3.3 70B)"
            }
            
        except Exception as e:
            logger.error("system_info_error", error=str(e))
            return {}
    
    @staticmethod
    async def get_running_processes(limit: int = 10) -> ToolResult:
        """Get list of running processes"""
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    processes.append(ProcessInfo(
                        pid=proc.info['pid'],
                        name=proc.info['name'],
                        cpu_percent=proc.info['cpu_percent'] or 0.0,
                        memory_percent=proc.info['memory_percent'] or 0.0,
                        status=proc.info['status']
                    ))
                except:
                    continue
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x.cpu_percent, reverse=True)
            
            return ToolResult(
                success=True,
                tool="get_processes",
                message=f"Retrieved {len(processes[:limit])} processes",
                data={"processes": [p.dict() for p in processes[:limit]]}
            )
            
        except Exception as e:
            logger.error("processes_error", error=str(e))
            return ToolResult(
                success=False,
                tool="get_processes",
                error={"code": "EXECUTION_ERROR", "message": str(e)}
            )


system_tools = SystemTools()
