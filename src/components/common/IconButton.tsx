"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  active?: boolean;
  variant?: "default" | "red" | "ghost";
}

export function IconButton({
  children,
  active,
  variant = "default",
  className,
  ...props
}: IconButtonProps) {
  return (
    <button
      className={cn(
        "p-2 rounded-lg transition-all duration-200 flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff1f2d]",
        variant === "default" && "bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white border border-white/10",
        variant === "red" && "bg-[#ff1f2d]/20 hover:bg-[#ff1f2d]/30 text-[#ff3344] border border-[#ff1f2d]/40 shadow-[0_0_12px_rgba(255,31,45,0.2)]",
        variant === "ghost" && "text-zinc-400 hover:text-white hover:bg-white/5",
        active && "border-[#ff1f2d] text-[#ff3344] bg-[#ff1f2d]/10",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
