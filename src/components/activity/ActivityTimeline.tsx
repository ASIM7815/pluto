"use client";

import React from "react";
import { Activity } from "@/types";
import { ActivityItem } from "./ActivityItem";

interface ActivityTimelineProps {
  activities: Activity[];
}

export function ActivityTimeline({ activities }: ActivityTimelineProps) {
  if (activities.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-zinc-500 font-mono">
        No recent activities logged.
      </div>
    );
  }

  return (
    <div className="space-y-1 pt-1">
      {activities.map((act) => (
        <ActivityItem key={act.id} activity={act} />
      ))}
    </div>
  );
}
