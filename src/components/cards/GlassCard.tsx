"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  hoverEffect?: boolean;
  glow?: boolean;
}

export function GlassCard({
  children,
  hoverEffect = false,
  glow = false,
  className,
  ...props
}: GlassCardProps) {
  return (
    <div
      className={cn(
        "glass-panel rounded-2xl p-5 border border-white/10 text-zinc-100 backdrop-blur-xl relative overflow-hidden",
        hoverEffect && "glass-panel-hover hover:-translate-y-0.5 cursor-pointer",
        glow && "border-[#ff1f2d]/30 shadow-[0_0_25px_rgba(255,31,45,0.12)]",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
