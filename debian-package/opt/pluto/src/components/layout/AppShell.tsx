"use client";

import React from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { usePlutoStore } from "@/store/plutoStore";
import { ConfirmationDialog } from "../cards/ConfirmationDialog";

interface AppShellProps {
  children: React.ReactNode;
  rightPanel?: React.ReactNode;
}

export function AppShell({ children, rightPanel }: AppShellProps) {
  const confirmationRequired = usePlutoStore((s) => s.confirmationRequired);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#050506] text-[#f5f5f5] bg-hud-grid">
      {/* Top Header */}
      <TopBar />

      {/* Main Grid Workspace Container */}
      <div className="flex-1 flex min-h-0 relative">
        {/* Left Sidebar */}
        <Sidebar />

        {/* Center Main Workspace */}
        <main className="flex-1 min-w-0 h-full overflow-y-auto p-4 lg:p-6 flex flex-col justify-between">
          {children}
        </main>

        {/* Right System & Activity Panel (360-390px) */}
        {rightPanel && (
          <aside className="hidden xl:flex w-[370px] shrink-0 h-full border-l border-white/10 p-5 flex-col gap-5 overflow-y-auto bg-[#050506]/80 backdrop-blur-lg">
            {rightPanel}
          </aside>
        )}
      </div>

      {/* Confirmation Modal Overlay */}
      {confirmationRequired && <ConfirmationDialog data={confirmationRequired} />}
    </div>
  );
}
