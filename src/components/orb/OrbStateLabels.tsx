"use client";

import React from "react";
import { PlutoState } from "@/types";
import { cn } from "@/lib/utils";

interface OrbStateLabelsProps {
  state: PlutoState;
}

export function OrbStateLabels({ state }: OrbStateLabelsProps) {
  const statesList: { id: PlutoState; label: string }[] = [
    { id: "listening", label: "LISTENING" },
    { id: "understanding", label: "UNDERSTANDING" },
    { id: "thinking", label: "THINKING" },
    { id: "planning", label: "PLANNING" },
    { id: "executing", label: "EXECUTING" },
    { id: "observing", label: "OBSERVING" },
    { id: "reasoning", label: "REASONING" },
    { id: "speaking", label: "SPEAKING" }
  ];

  return (
    <div className="absolute inset-0 pointer-events-none flex items-center justify-between px-4 sm:px-12 select-none">
      {/* Left HUD Label - Active Voice Status */}
      <div className="flex flex-col items-start gap-2">
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-full backdrop-blur-md border text-[11px] font-mono tracking-widest transition-all duration-300",
            state === "listening"
              ? "bg-[#ff1f2d]/20 border-[#ff1f2d] text-white shadow-[0_0_15px_rgba(255,31,45,0.4)]"
              : "bg-black/30 border-white/10 text-zinc-500"
          )}
        >
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              state === "listening" ? "bg-[#ff1f2d] animate-ping" : "bg-zinc-600"
            )}
          />
          <span>○ LISTENING</span>

          {/* Animated Waveform when listening */}
          {state === "listening" && (
            <div className="flex items-center gap-0.5 ml-1 h-3">
              <span className="w-0.5 h-full bg-[#ff3344] animate-[bounce_1s_infinite_100ms]" />
              <span className="w-0.5 h-full bg-[#ff3344] animate-[bounce_1s_infinite_300ms]" />
              <span className="w-0.5 h-full bg-[#ff3344] animate-[bounce_1s_infinite_200ms]" />
            </div>
          )}
        </div>

        <div className="text-[10px] text-zinc-600 font-mono pl-2">
          VOICE HUD • LOCAL WHISPER
        </div>
      </div>

      {/* Right HUD Labels - AI Processing Pipeline */}
      <div className="flex flex-col items-end gap-1.5 font-mono text-[10px]">
        {statesList.map((item) => {
          const isActive = state === item.id;
          return (
            <div
              key={item.id}
              className={cn(
                "flex items-center gap-2 transition-all duration-300",
                isActive
                  ? "text-[#ff3344] font-bold text-xs tracking-wider scale-105"
                  : "text-zinc-600 opacity-60"
              )}
            >
              <span>{isActive ? "●" : "○"}</span>
              <span>{item.label}</span>
            </div>
          );
        })}

        <div
          className={cn(
            "flex items-center gap-2 mt-2 pt-2 border-t border-white/5 transition-all duration-300",
            state === "idle" ? "text-emerald-400 font-medium" : "text-zinc-600 opacity-50"
          )}
        >
          <span>{state === "idle" ? "●" : "○"}</span>
          <span>READY</span>
        </div>
      </div>
    </div>
  );
}
