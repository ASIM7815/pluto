import { SystemMetrics } from "@/types";

const REST_BASE = "/api/backend";

let currentMetrics: SystemMetrics = {
  cpu: 23,
  ram: 41,
  storage: 68,
  gpu: 14,
  temp: 42,
  networkUp: "1.2 MB/s",
  networkDown: "8.4 MB/s"
};

export const systemService = {
  async getMetrics(): Promise<SystemMetrics> {
    try {
      // Try to fetch real metrics from backend
      const response = await fetch(`${REST_BASE}/system/metrics`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const metrics = await response.json();
        currentMetrics = metrics;
        return metrics;
      }
    } catch {
      console.log("⚠️ Using mock metrics (backend not available)");
    }

    // Fallback: Add subtle fluctuation to mock data
    const cpuDelta = (Math.random() - 0.5) * 4;
    const ramDelta = (Math.random() - 0.5) * 2;
    
    currentMetrics = {
      ...currentMetrics,
      cpu: Math.min(99, Math.max(12, Math.round(currentMetrics.cpu + cpuDelta))),
      ram: Math.min(95, Math.max(30, Math.round(currentMetrics.ram + ramDelta))),
      gpu: Math.min(90, Math.max(8, Math.round(14 + (Math.random() - 0.5) * 6)))
    };

    return currentMetrics;
  },

  async getSystemInfo() {
    try {
      const response = await fetch(`${REST_BASE}/system/info`);
      if (response.ok) {
        return await response.json();
      }
    } catch {
      console.log("⚠️ Using mock system info");
    }

    // Fallback mock data
    return {
      os: "Linux x86_64",
      distro: "Ubuntu 26.04 LTS (PLUTO Kernel 6.12.4)",
      host: "PLUTO-DESKTOP-NEO",
      uptime: "4h 38m",
      securityStatus: "Encrypted & Isolated",
      voiceEngine: "PLUTO ElevenLabs TTS",
      llmEngine: "GPT-OSS Llama 3.3 70B"
    };
  }
};
