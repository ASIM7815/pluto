"use client";

import { useState, useEffect } from "react";
import { systemService } from "@/services/system";
import { SystemMetrics } from "@/types";

export function useSystemStats(pollIntervalMs = 3000) {
  // Start with null to avoid hydration mismatch
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);

  useEffect(() => {
    // Set initial metrics on client side only
    setMetrics(systemService.getMetrics());

    const timer = setInterval(() => {
      setMetrics(systemService.getMetrics());
    }, pollIntervalMs);

    return () => clearInterval(timer);
  }, [pollIntervalMs]);

  // Return static values during SSR, then switch to dynamic on client
  return metrics || {
    cpu: 23,
    ram: 41,
    storage: 68,
    gpu: 14,
    temp: 42,
    networkUp: "1.2 MB/s",
    networkDown: "8.4 MB/s"
  };
}
