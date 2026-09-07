"use client";

import React, { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { PlutoOrb } from "@/components/orb/PlutoOrb";
import { CommandBar } from "@/components/command/CommandBar";
import { QuickActions } from "@/components/actions/QuickActions";
import { ExecutionPanel } from "@/components/command/ExecutionPanel";
import { ProductivityCard } from "@/components/cards/ProductivityCard";
import { ActionPreviewCard } from "@/components/cards/ActionPreviewCard";
import { ErrorCard } from "@/components/cards/ErrorCard";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { ResponseDisplay } from "@/components/common/ResponseDisplay";
import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "@/services/ai";

const productivityCardsList = [
  {
    id: "prod-1",
    title: "Boost Productivity",
    description: "Open apps, manage files, automate repetitive OS tasks.",
    iconName: "Zap",
    actionCommand: "Open VS Code and start my project"
  },
  {
    id: "prod-2",
    title: "Explore the Web",
    description: "Search, extract, and synthesize live browser insights.",
    iconName: "Compass",
    actionCommand: "Open YouTube and play a great song"
  },
  {
    id: "prod-3",
    title: "Work Smarter",
    description: "Orchestrate complex Linux workflows in seconds.",
    iconName: "Cpu",
    actionCommand: "Create a folder called PLUTO inside my Projects directory"
  },
  {
    id: "prod-4",
    title: "Stay in Control",
    description: "Full local privacy, sandboxed & verified OS actions.",
    iconName: "ShieldCheck",
    actionCommand: "Check system status and optimize memory"
  }
];

export default function HomePage() {
  const state = usePlutoStore((s) => s.state);
  const actionPreview = usePlutoStore((s) => s.actionPreview);
  const errorMessage = usePlutoStore((s) => s.errorMessage);
  const intent = usePlutoStore((s) => s.intent);
  const confidence = usePlutoStore((s) => s.confidence);
  const recommendedTools = usePlutoStore((s) => s.recommendedTools);

  // Connect to backend WebSocket on mount
  useEffect(() => {
    console.log("🚀 Connecting to PLUTO backend...");
    aiService.connectWebSocket();
  }, []);

  return (
    <AppShell rightPanel={<RightPanelContent />}>
      <div className="flex flex-col justify-between items-center h-full max-w-[1050px] mx-auto w-full gap-2">
        {/* Central Workspace Header & Orb */}
        <div className="flex flex-col items-center justify-center w-full relative">
          <PlutoOrb
            state={state}
            size={390}
            intent={intent}
            confidence={confidence}
            recommendedTools={recommendedTools}
          />

          {/* PLUTO Title Branding */}
          <div className="text-center mt-1 select-none">
            <h2 className="text-3xl sm:text-4xl font-light tracking-[0.3em] text-white flex items-center justify-center font-sans">
              P L U T
              <span className="text-[#ff1f2d] font-normal glow-o">
                O
              </span>
            </h2>
            <p className="text-[10px] sm:text-xs font-mono tracking-[0.25em] text-zinc-400 uppercase mt-1">
              W H A T &nbsp; C A N &nbsp; I &nbsp; D O &nbsp; F O R &nbsp; Y O U ?
            </p>
          </div>
        </div>

        {/* Dynamic Overlays: Action Preview or Error Card */}
        {actionPreview && <ActionPreviewCard preview={actionPreview} />}
        {errorMessage && <ErrorCard message={errorMessage} />}

        {/* Command Bar & Quick Actions */}
        <div className="w-full my-2">
          <CommandBar />
          <QuickActions />
          <ExecutionPanel />
        </div>

        {/* Productivity Cards Grid (4 Columns at bottom) */}
        <div className="w-full grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-2">
          {productivityCardsList.map((card) => (
            <ProductivityCard key={card.id} {...card} />
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function RightPanelContent() {
  return (
    <>
      <SystemOverview />
      <ResponseDisplay />
      <ActivityPanel />
    </>
  );
}
