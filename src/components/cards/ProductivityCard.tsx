"use client";

import React from "react";
import { ArrowUpRight, Zap, Compass, Cpu, ShieldCheck, LucideIcon } from "lucide-react";
import { GlassCard } from "./GlassCard";
import { aiService } from "@/services/ai";

const iconMap: Record<string, LucideIcon> = {
  Zap,
  Compass,
  Cpu,
  ShieldCheck
};

interface ProductivityCardProps {
  id: string;
  title: string;
  description: string;
  iconName: string;
  actionCommand: string;
}

export function ProductivityCard({
  title,
  description,
  iconName,
  actionCommand
}: ProductivityCardProps) {
  const Icon = iconMap[iconName] || Zap;

  const handleClick = () => {
    aiService.executeCommand(actionCommand);
  };

  return (
    <GlassCard
      hoverEffect
      onClick={handleClick}
      className="group flex flex-col justify-between h-full p-4 transition-all duration-300 hover:border-[#ff1f2d]/40"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="p-2 rounded-xl bg-[#ff1f2d]/10 border border-[#ff1f2d]/20 text-[#ff3344] group-hover:scale-110 transition-transform duration-300">
          <Icon className="w-5 h-5" />
        </div>
        <ArrowUpRight className="w-4 h-4 text-zinc-500 group-hover:text-[#ff3344] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
      </div>

      <div>
        <h4 className="text-sm font-semibold text-zinc-100 group-hover:text-white mb-1 transition-colors">
          {title}
        </h4>
        <p className="text-xs text-zinc-400 leading-relaxed">
          {description}
        </p>
      </div>
    </GlassCard>
  );
}
