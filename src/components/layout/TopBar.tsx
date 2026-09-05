"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck, Command, Maximize, Minimize } from "lucide-react";
import { WindowControls } from "./WindowControls";
import { voiceService } from "@/services/voice";
import { usePlutoStore } from "@/store/plutoStore";

export function TopBar() {
  const store = usePlutoStore();
  const [isFullscreen, setIsFullscreen] = useState(false);

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

  // Fullscreen change handler
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  // Toggle fullscreen
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        console.error("Error attempting to enable fullscreen:", err);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  };

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

        <span className="text-zinc-700">│</span>

        {/* Fullscreen Toggle Button */}
        <button
          onClick={toggleFullscreen}
          className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 hover:border-[#ff1f2d]/30 transition-all flex items-center justify-center group"
          title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
        >
          {isFullscreen ? (
            <Minimize className="w-3.5 h-3.5 text-zinc-400 group-hover:text-[#ff3344]" />
          ) : (
            <Maximize className="w-3.5 h-3.5 text-zinc-400 group-hover:text-[#ff3344]" />
          )}
        </button>

        {/* Window controls for Tauri desktop packaging */}
        <WindowControls />
      </div>
    </header>
  );
}
