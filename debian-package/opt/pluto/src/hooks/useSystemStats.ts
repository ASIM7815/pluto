"use client";

import { useState, useEffect } from "react";
import { systemService } from "@/services/system";
import { SystemMetrics } from "@/types";

const DEFAULT_METRICS: SystemMetrics = {
  cpu: 23,
  ram: 41,
  storage: 68,
  gpu: 14,
  temp: 42,
  networkUp: "1.2 MB/s",
  networkDown: "8.4 MB/s"
};

export function useSystemStats(pollIntervalMs = 3000) {
  const [metrics, setMetrics] = useState<SystemMetrics>(DEFAULT_METRICS);

  useEffect(() => {
    // Fetch initial metrics
    const fetchMetrics = async () => {
      try {
        const data = await systemService.getMetrics();
        setMetrics(data);
      } catch (error) {
        console.error("Failed to fetch metrics:", error);
        setMetrics(DEFAULT_METRICS);
      }
    };

    fetchMetrics();

    const timer = setInterval(() => {
      fetchMetrics();
    }, pollIntervalMs);

    return () => clearInterval(timer);
  }, [pollIntervalMs]);

  return metrics;
}
