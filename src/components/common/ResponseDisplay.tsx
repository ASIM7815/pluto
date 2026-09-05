"use client";

import React from "react";
import { usePlutoStore } from "@/store/plutoStore";
import { MessageCircle, Sparkles } from "lucide-react";

export function ResponseDisplay() {
  const aiResponse = usePlutoStore((state) => state.aiResponse);
  const state = usePlutoStore((state) => state.state);

  if (!aiResponse) return null;

  const isVisible = state === "success" || state === "idle";

  return (
    <div 
      className={`
        transition-all duration-500 ease-out
        ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'}
      `}
    >
      <div className="glass-panel p-4 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-white/[0.02]">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500/20 to-pink-500/20 flex items-center justify-center border border-red-500/20">
              <Sparkles className="w-4 h-4 text-red-400" />
            </div>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <MessageCircle className="w-3.5 h-3.5 text-zinc-400" />
              <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                PLUTO Response
              </span>
            </div>
            
            <p className="text-sm text-zinc-100 leading-relaxed whitespace-pre-wrap">
              {aiResponse}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
