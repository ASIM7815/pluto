"use client";

import React from "react";
import { ActivityTimeline } from "./ActivityTimeline";
import { usePlutoStore } from "@/store/plutoStore";
import { Clock, ExternalLink } from "lucide-react";
import Link from "next/link";

export function ActivityPanel() {
  const activities = usePlutoStore((s) => s.activities);

  return (
    <div className="glass-panel p-5 rounded-2xl border border-white/10 flex-1 flex flex-col min-h-0">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/10">
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-300 uppercase tracking-wider">
          <Clock className="w-3.5 h-3.5 text-[#ff3344]" />
          <span>Recent Activity</span>
        </div>
        <Link
          href="/automations"
          className="text-[11px] text-zinc-400 hover:text-[#ff3344] flex items-center gap-1 transition-colors font-mono"
        >
          <span>See all</span>
          <ExternalLink className="w-3 h-3" />
        </Link>
      </div>

      <div className="overflow-y-auto max-h-[380px] pr-1">
        <ActivityTimeline activities={activities} />
      </div>
    </div>
  );
}
