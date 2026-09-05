"use client";

import React from "react";
import { Folder, MessageCircle, Monitor, AppWindow } from "lucide-react";
import { Activity } from "@/types";

interface ActivityItemProps {
  activity: Activity;
}

export function ActivityItem({ activity }: ActivityItemProps) {
  const getCategoryIcon = () => {
    switch (activity.category) {
      case "message":
        return <MessageCircle className="w-3.5 h-3.5 text-[#ff3344]" />;
      case "file":
        return <Folder className="w-3.5 h-3.5 text-zinc-300" />;
      case "system":
        return <Monitor className="w-3.5 h-3.5 text-emerald-400" />;
      case "app":
      default:
        return <AppWindow className="w-3.5 h-3.5 text-amber-400" />;
    }
  };

  const getStatusDot = () => {
    switch (activity.status) {
      case "running":
        return <span className="w-2 h-2 rounded-full bg-[#ff1f2d] animate-ping" />;
      case "success":
        return <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]" />;
      case "error":
        return <span className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]" />;
      case "info":
      default:
        return <span className="w-2 h-2 rounded-full bg-zinc-500" />;
    }
  };

  return (
    <div className="relative pl-6 pb-4 border-l border-white/10 last:pb-0 last:border-l-transparent group">
      {/* Timeline Bullet */}
      <div className="absolute -left-[5px] top-1 flex items-center justify-center bg-[#050506] p-0.5 rounded-full">
        {getStatusDot()}
      </div>

      <div className="bg-white/[0.02] group-hover:bg-white/[0.05] p-3 rounded-xl border border-white/5 group-hover:border-white/10 transition-all duration-200">
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-2">
            <span className="p-1 rounded-md bg-white/5 border border-white/5">
              {getCategoryIcon()}
            </span>
            <h4 className="text-xs font-semibold text-zinc-200 group-hover:text-white transition-colors">
              {activity.title}
            </h4>
          </div>
          <span className="text-[10px] text-zinc-500 font-mono">
            {activity.timestamp}
          </span>
        </div>

        <p className="text-xs text-zinc-400 font-mono line-clamp-2 pl-7 leading-relaxed">
          {activity.description}
        </p>
      </div>
    </div>
  );
}
