"use client";

import React from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/cards/GlassCard";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { Grid2X2, Play, Code, Globe, MessageCircle, Terminal, Image, Music, Settings } from "lucide-react";
import { aiService } from "@/services/ai";

const linuxApps = [
  { id: "vscode", name: "Visual Studio Code", category: "Development", icon: Code, command: "Open VS Code and start my project" },
  { id: "chrome", name: "Google Chrome", category: "Browser", icon: Globe, command: "Open YouTube and play a song" },
  { id: "whatsapp", name: "WhatsApp Desktop", category: "Social", icon: MessageCircle, command: "Open WhatsApp and send Owais a message" },
  { id: "terminal", name: "Linux Terminal", category: "System", icon: Terminal, command: "Open terminal" },
  { id: "gimp", name: "GIMP Image Editor", category: "Graphics", icon: Image, command: "Open GIMP editor" },
  { id: "spotify", name: "Spotify Player", category: "Audio", icon: Music, command: "Play music on Spotify" },
  { id: "settings", name: "Control Center", category: "System", icon: Settings, command: "Check system status" }
];

export default function AppsPage() {
  const handleLaunch = (cmd: string) => {
    aiService.executeCommand(cmd);
  };

  return (
    <AppShell rightPanel={<AppsRightPanel />}>
      <div className="flex flex-col h-full max-w-5xl mx-auto w-full gap-5">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h2 className="text-xl font-light text-white tracking-wider flex items-center gap-2">
              <Grid2X2 className="w-5 h-5 text-[#ff3344]" />
              Linux Applications Grid
            </h2>
            <p className="text-xs text-zinc-400">Launch and orchestrate desktop Linux software via PLUTO</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {linuxApps.map((app) => {
            const Icon = app.icon;
            return (
              <GlassCard
                key={app.id}
                hoverEffect
                onClick={() => handleLaunch(app.command)}
                className="group flex items-center justify-between p-4 border-white/10 hover:border-[#ff1f2d]/50"
              >
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-[#ff1f2d]/10 border border-[#ff1f2d]/25 text-[#ff3344] group-hover:scale-110 transition-transform">
                    <Icon className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-100 group-hover:text-white">
                      {app.name}
                    </h4>
                    <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider">
                      {app.category}
                    </span>
                  </div>
                </div>

                <button className="p-2 rounded-lg bg-white/5 group-hover:bg-[#ff1f2d] text-zinc-400 group-hover:text-white transition-all">
                  <Play className="w-4 h-4 fill-current" />
                </button>
              </GlassCard>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}

function AppsRightPanel() {
  return (
    <>
      <SystemOverview />
      <ActivityPanel />
    </>
  );
}
