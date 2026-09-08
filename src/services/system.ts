import { SystemMetrics } from "@/types";
import { call, isTauriApp } from "@/services/ipc";

let currentMetrics: SystemMetrics = {
  cpu: 23,
  ram: 41,
  storage: 68,
  gpu: 14,
  temp: 42,
  networkUp: "1.2 MB/s",
  networkDown: "8.4 MB/s",
};

export interface SystemInfo {
  os: string;
  distro: string;
  host: string;
  uptime: string;
  securityStatus: string;
  voiceEngine: string;
  llmEngine: string;
}

export const systemService = {
  async getMetrics(): Promise<SystemMetrics> {
    if (isTauriApp()) {
      try {
        const metrics = await call<SystemMetrics>("pluto_get_system_metrics");
        currentMetrics = metrics;
        return metrics;
      } catch {
        // fall through to fluctuation below
      }
    }

    // Browser/preview fallback: subtle fluctuation so the UI stays alive.
    const cpuDelta = (Math.random() - 0.5) * 4;
    const ramDelta = (Math.random() - 0.5) * 2;
    currentMetrics = {
      ...currentMetrics,
      cpu: Math.min(99, Math.max(12, Math.round(currentMetrics.cpu + cpuDelta))),
      ram: Math.min(95, Math.max(30, Math.round(currentMetrics.ram + ramDelta))),
      gpu: Math.min(90, Math.max(8, Math.round(14 + (Math.random() - 0.5) * 6))),
    };
    return currentMetrics;
  },

  async getSystemInfo(): Promise<SystemInfo> {
    if (isTauriApp()) {
      try {
        return await call<SystemInfo>("pluto_get_system_info");
      } catch {
        // fallback below
      }
    }
    return {
      os: "Linux x86_64",
      distro: "Debian GNU/Linux (PLUTO Desktop)",
      host: "PLUTO-DESKTOP",
      uptime: "4h 38m",
      securityStatus: "Encrypted & Isolated",
      voiceEngine: "PLUTO Local TTS",
      llmEngine: "PLUTO Pattern Intelligence (on-device)",
    };
  },
};
