"use client";

import React from "react";
import { Video, MessageCircle, Folder, Music, Code2, FolderPlus, LucideIcon } from "lucide-react";
import { aiService } from "@/services/ai";

const iconMap: Record<string, LucideIcon> = {
  Youtube: Video,
  MessageCircle,
  Folder,
  Music,
  Code2,
  FolderPlus
};

interface QuickActionProps {
  id: string;
  label: string;
  iconName: string;
  command: string;
}

export function QuickAction({ label, iconName, command }: QuickActionProps) {
  const Icon = iconMap[iconName] || Folder;

  const handleClick = () => {
    aiService.executeCommand(command);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="px-3.5 py-1.5 rounded-full bg-white/[0.03] hover:bg-[#ff1f2d]/15 border border-white/10 hover:border-[#ff1f2d]/50 text-zinc-300 hover:text-white text-xs font-mono flex items-center gap-2 transition-all duration-200 cursor-pointer hover:shadow-[0_0_15px_rgba(255,31,45,0.2)] hover:scale-105 active:scale-95 shrink-0"
    >
      <Icon className="w-3.5 h-3.5 text-[#ff3344]" />
      <span>{label}</span>
    </button>
  );
}
