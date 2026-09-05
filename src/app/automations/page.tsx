"use client";

import React from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/cards/GlassCard";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { Zap, Play, Plus } from "lucide-react";
import { aiService } from "@/services/ai";

const automationsList = [
  {
    id: "a-1",
    name: "Morning Focus Sequence",
    trigger: "Voice Command: 'Morning Focus'",
    actions: ["Open VS Code", "Launch Chrome -> Lofi Music", "Check System Status"],
    status: "Active"
  },
  {
    id: "a-2",
    name: "Developer Workspace Init",
    trigger: "Folder Creation: ~/Projects/*",
    actions: ["Initialize Git Repo", "Create boilerplate README", "Open Terminal"],
    status: "Active"
  },
  {
    id: "a-3",
    name: "Memory Guard Watchdog",
    trigger: "System Condition: RAM > 85%",
    actions: ["Notify User", "Purge temp cache files", "Optimize background tasks"],
    status: "Active"
  }
];

export default function AutomationsPage() {
  const handleTrigger = (name: string) => {
    aiService.executeCommand(`Run automation trigger: ${name}`);
  };

  return (
    <AppShell rightPanel={<AutomationsRightPanel />}>
      <div className="flex flex-col h-full max-w-5xl mx-auto w-full gap-5">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h2 className="text-xl font-light text-white tracking-wider flex items-center gap-2">
              <Zap className="w-5 h-5 text-[#ff3344]" />
              PLUTO Workflow Automations
            </h2>
            <p className="text-xs text-zinc-400">Autonomous Linux desktop triggers & multi-step AI pipelines</p>
          </div>

          <button
            onClick={() => aiService.executeCommand("Create a new workflow automation")}
            className="px-3.5 py-1.5 rounded-xl bg-[#ff1f2d] hover:bg-[#ff3344] text-white text-xs font-mono flex items-center gap-2 transition-all cursor-pointer shadow-[0_0_15px_rgba(255,31,45,0.4)]"
          >
            <Plus className="w-4 h-4" />
            <span>New Automation</span>
          </button>
        </div>

        <div className="space-y-4">
          {automationsList.map((item) => (
            <GlassCard key={item.id} className="p-5 border-white/10 bg-[#09090d]">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-[#ff1f2d]/10 border border-[#ff1f2d]/30 text-[#ff3344]">
                    <Zap className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-base font-semibold text-white">{item.name}</h4>
                    <p className="text-xs text-zinc-400 font-mono mt-0.5">{item.trigger}</p>
                  </div>
                </div>

                <button
                  onClick={() => handleTrigger(item.name)}
                  className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-[#ff1f2d] text-zinc-300 hover:text-white border border-white/10 text-xs font-mono flex items-center gap-2 transition-all cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Test Run</span>
                </button>
              </div>

              <div className="pt-3 border-t border-white/5 flex flex-wrap gap-2 text-xs font-mono">
                <span className="text-zinc-500 uppercase text-[10px]">Steps:</span>
                {item.actions.map((act, i) => (
                  <span key={i} className="px-2 py-0.5 rounded bg-white/5 border border-white/5 text-zinc-300">
                    {i + 1}. {act}
                  </span>
                ))}
              </div>
            </GlassCard>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function AutomationsRightPanel() {
  return (
    <>
      <SystemOverview />
      <ActivityPanel />
    </>
  );
}
