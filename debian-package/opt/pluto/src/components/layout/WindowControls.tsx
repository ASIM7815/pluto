"use client";

import React from "react";
import { Minus, Square, X } from "lucide-react";

export function WindowControls() {
  return (
    <div className="flex items-center gap-1.5 pl-3 border-l border-white/10">
      <button
        type="button"
        className="p-1 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-white/10 transition-colors"
        title="Minimize"
      >
        <Minus className="w-3 h-3" />
      </button>
      <button
        type="button"
        className="p-1 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-white/10 transition-colors"
        title="Maximize"
      >
        <Square className="w-2.5 h-2.5" />
      </button>
      <button
        type="button"
        className="p-1 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/20 transition-colors"
        title="Close"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}
