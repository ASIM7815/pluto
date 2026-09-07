"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface GlowButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost";
}

export function GlowButton({
  children,
  variant = "primary",
  className,
  ...props
}: GlowButtonProps) {
  return (
    <button
      className={cn(
        "px-4 py-2 rounded-xl font-medium text-xs tracking-wider uppercase transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff1f2d]",
        variant === "primary" &&
          "bg-[#ff1f2d] hover:bg-[#ff3344] text-white border border-[#ff3344] shadow-[0_0_20px_rgba(255,31,45,0.4)] hover:shadow-[0_0_28px_rgba(255,31,45,0.6)] active:scale-95",
        variant === "secondary" &&
          "bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 hover:border-white/20 active:scale-95",
        variant === "danger" &&
          "bg-red-950/60 hover:bg-red-900/80 text-red-200 border border-red-500/40 shadow-[0_0_15px_rgba(220,38,38,0.3)] active:scale-95",
        variant === "ghost" &&
          "bg-transparent hover:bg-white/5 text-zinc-400 hover:text-white border border-transparent",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
