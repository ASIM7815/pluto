"use client";

import React, { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/cards/GlassCard";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { Monitor, Cpu, HardDrive, Activity, RefreshCw } from "lucide-react";
import { useSystemStats } from "@/hooks/useSystemStats";
import { systemService } from "@/services/system";
import { aiService } from "@/services/ai";

interface SystemInfo {
  os?: string;
  distro?: string;
  host?: string;
  uptime?: string;
  voiceEngine?: string;
  llmEngine?: string;
}

export default function SystemPage() {
  const metrics = useSystemStats(2000);
  const [sysInfo, setSysInfo] = useState<SystemInfo>({
    os: "Linux",
    distro: "Loading...",
    host: "-",
    uptime: "-",
    voiceEngine: "PLUTO Piper / pico2wave / espeak-ng (local)",
    llmEngine: "PLUTO Pattern Intelligence (on-device)",
  });

  useEffect(() => {
    systemService.getSystemInfo().then(setSysInfo).catch(() => {});
  }, []);

  return (
    <AppShell rightPanel={<SystemRightPanel />}>
      <div className="flex flex-col h-full max-w-5xl mx-auto w-full gap-5">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h2 className="text-xl font-light text-white tracking-wider flex items-center gap-2">
              <Monitor className="w-5 h-5 text-[#ff3344]" />
              System Diagnostics & AI Kernel
            </h2>
            <p className="text-xs text-zinc-400">Real-time Linux hardware metrics and sandboxed execution environment</p>
          </div>

          <button
            onClick={() => aiService.executeCommand("Check system status and optimize memory")}
            className="px-3.5 py-1.5 rounded-xl bg-[#ff1f2d]/20 hover:bg-[#ff1f2d]/30 text-[#ff3344] border border-[#ff1f2d]/40 text-xs font-mono flex items-center gap-2 transition-all cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Optimize System</span>
          </button>
        </div>

        {/* Live Gauges */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <GlassCard className="p-4 bg-[#09090d]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-zinc-400 uppercase">CPU Usage</span>
              <Cpu className="w-4 h-4 text-[#ff3344]" />
            </div>
            <div className="text-2xl font-bold font-mono text-white mb-2">{metrics.cpu}%</div>
            <div className="w-full bg-white/10 rounded-full h-1.5">
              <div
                className="bg-[#ff1f2d] h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${metrics.cpu}%` }}
              />
            </div>
          </GlassCard>

          <GlassCard className="p-4 bg-[#09090d]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-zinc-400 uppercase">RAM Usage</span>
              <Activity className="w-4 h-4 text-[#ff3344]" />
            </div>
            <div className="text-2xl font-bold font-mono text-white mb-2">{metrics.ram}%</div>
            <div className="w-full bg-white/10 rounded-full h-1.5">
              <div
                className="bg-[#ff3344] h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${metrics.ram}%` }}
              />
            </div>
          </GlassCard>

          <GlassCard className="p-4 bg-[#09090d]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-zinc-400 uppercase">Disk Storage</span>
              <HardDrive className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold font-mono text-white mb-2">{metrics.storage}%</div>
            <div className="w-full bg-white/10 rounded-full h-1.5">
              <div
                className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${metrics.storage}%` }}
              />
            </div>
          </GlassCard>
        </div>

        {/* Kernel & Models Info */}
        <GlassCard className="p-5 space-y-3 bg-[#08080b]">
          <h3 className="text-sm font-semibold text-white uppercase tracking-wider font-mono text-[#ff3344]">
            Linux OS & AI Engine Metadata
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-zinc-500">Operating System:</span>
              <p className="text-zinc-200 mt-0.5">{sysInfo.os} ({sysInfo.distro})</p>
            </div>
            <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-zinc-500">Host Hardware:</span>
              <p className="text-zinc-200 mt-0.5">{sysInfo.host} (Uptime: {sysInfo.uptime})</p>
            </div>
            <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-zinc-500">Voice Recognition Engine:</span>
              <p className="text-zinc-200 mt-0.5">{sysInfo.voiceEngine}</p>
            </div>
            <div className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-zinc-500">Primary Intelligence Core:</span>
              <p className="text-zinc-200 mt-0.5">{sysInfo.llmEngine}</p>
            </div>
          </div>
        </GlassCard>
      </div>
    </AppShell>
  );
}

function SystemRightPanel() {
  return (
    <>
      <SystemOverview />
      <ActivityPanel />
    </>
  );
}
