"use client";

import React from "react";
import { MetricRing } from "./MetricRing";
import { useSystemStats } from "@/hooks/useSystemStats";
import { Cpu, Layers } from "lucide-react";

export function SystemOverview() {
  const metrics = useSystemStats(2500);

  return (
    <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-5">
      <div>
        <h3 className="text-base font-normal text-zinc-100 mb-1">
          Good Afternoon, <span className="font-semibold text-white">Asim</span>
        </h3>
        <p className="text-xs text-zinc-400">
          Ready to turn your ideas into actions.
        </p>
      </div>

      {/* Metric Rings Grid */}
      <div className="grid grid-cols-3 gap-2 py-3 px-2 rounded-xl bg-black/40 border border-white/5">
        <MetricRing label="CPU" value={metrics.cpu} color="#ff1f2d" />
        <MetricRing label="RAM" value={metrics.ram} color="#ff3344" />
        <MetricRing label="Storage" value={metrics.storage} color="#e11d48" />
      </div>

      {/* System Quick Specs */}
      <div className="space-y-2 pt-1">
        <div className="flex items-center justify-between text-xs px-2 py-1.5 rounded-lg bg-white/[0.02] border border-white/5">
          <div className="flex items-center gap-2 text-zinc-400">
            <Cpu className="w-3.5 h-3.5 text-zinc-500" />
            <span>GPU Load</span>
          </div>
          <span className="font-mono text-zinc-200">{metrics.gpu ?? 14}%</span>
        </div>

        <div className="flex items-center justify-between text-xs px-2 py-1.5 rounded-lg bg-white/[0.02] border border-white/5">
          <div className="flex items-center gap-2 text-zinc-400">
            <Layers className="w-3.5 h-3.5 text-zinc-500" />
            <span>Network</span>
          </div>
          <span className="font-mono text-zinc-300 text-[11px]">
            ↑ {metrics.networkUp} • ↓ {metrics.networkDown}
          </span>
        </div>
      </div>
    </div>
  );
}
