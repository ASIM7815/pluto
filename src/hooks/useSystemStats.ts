"use client";

import { useState, useEffect } from "react";
import { systemService } from "@/services/system";
import { SystemMetrics } from "@/types";

export function useSystemStats(pollIntervalMs = 3000) {
  const [metrics, setMetrics] = useState<SystemMetrics>(() => systemService.getMetrics());

  useEffect(() => {
    const timer = setInterval(() => {
      setMetrics(systemService.getMetrics());
    }, pollIntervalMs);

    return () => clearInterval(timer);
  }, [pollIntervalMs]);

  return metrics;
}
