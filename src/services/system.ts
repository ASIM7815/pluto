import { SystemMetrics } from "@/types";

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
  getMetrics(): SystemMetrics {
    // Add subtle real-time fluctuation
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

  getSystemInfo() {
    return {
      os: "Linux x86_64",
      distro: "Ubuntu 26.04 LTS (PLUTO Kernel 6.12.4)",
      host: "PLUTO-DESKTOP-NEO",
      uptime: "4h 38m",
      securityStatus: "Encrypted & Isolated",
      voiceEngine: "PLUTO Local Whisper-v3",
      llmEngine: "PLUTO Quantum-1 70B (Local GPU)"
    };
  }
};
