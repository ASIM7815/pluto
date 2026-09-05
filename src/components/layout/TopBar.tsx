"use client";

import React, { useEffect } from "react";
import { ShieldCheck, Command } from "lucide-react";
import { WindowControls } from "./WindowControls";
import { voiceService } from "@/services/voice";
import { usePlutoStore } from "@/store/plutoStore";

export function TopBar() {
  const store = usePlutoStore();

  // Keyboard Shortcut Handler for Ctrl + Space / Esc
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.code === "Space") {
        e.preventDefault();
        voiceService.toggleListening();
      } else if (e.key === "Escape") {
        store.resetToIdle();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [store]);

  return (
    <header className="h-14 px-6 border-b border-white/10 bg-[#050506]/90 backdrop-blur-md flex items-center justify-between z-30 shrink-0 select-none">
      {/* Left Shortcut Hint */}
      <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-zinc-300">
          <Command className="w-3 h-3 text-[#ff3344]" />
          <span className="font-semibold text-white">Ctrl + Space</span>
        </span>
        <span className="hidden sm:inline text-zinc-500">to talk to PLUTO</span>
      </div>

      {/* Right User & System Status */}
      <div className="flex items-center gap-4 text-xs font-mono">
        {/* Status Indicator */}
        <div className="flex items-center gap-2 text-zinc-300">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span>Online</span>
        </div>

        <span className="text-zinc-700">│</span>

        {/* Security badge */}
        <div className="hidden md:flex items-center gap-1.5 text-zinc-400">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Local & Secure</span>
        </div>

        <span className="text-zinc-700 hidden md:inline">│</span>

        {/* User Profile Avatar */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-[#ff1f2d] to-zinc-800 border border-[#ff1f2d]/50 flex items-center justify-center text-white text-xs font-bold shadow-[0_0_10px_rgba(255,31,45,0.3)]">
            A
          </div>
          <span className="hidden lg:inline text-zinc-200 font-sans font-medium">Asim</span>
        </div>

        {/* Window controls for Tauri desktop packaging */}
        <WindowControls />
      </div>
    </header>
  );
}
