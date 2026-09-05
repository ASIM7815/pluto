"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface StatusIndicatorProps {
  status: "online" | "offline" | "busy" | "working";
  label?: string;
  className?: string;
}

export function StatusIndicator({ status, label, className }: StatusIndicatorProps) {
  const colorMap = {
    online: "bg-emerald-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]",
    offline: "bg-zinc-500",
    busy: "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]",
    working: "bg-[#ff1f2d] shadow-[0_0_10px_rgba(255,31,45,0.8)] animate-ping"
  };

  return (
    <div className={cn("inline-flex items-center gap-2 text-xs text-zinc-400 font-mono", className)}>
      <span className="relative flex h-2 w-2">
        {status === "working" && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#ff1f2d] opacity-75"></span>
        )}
        <span className={cn("relative inline-flex rounded-full h-2 w-2", colorMap[status])}></span>
      </span>
      {label && <span>{label}</span>}
    </div>
  );
}
