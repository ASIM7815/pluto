"use client";

import React from "react";
import { QuickAction } from "./QuickAction";

const quickActionsList = [
  { id: "youtube", label: "Open YouTube", iconName: "Youtube", command: "Open YouTube and play a great song" },
  { id: "whatsapp", label: "Message Owais", iconName: "MessageCircle", command: "Open WhatsApp and send Owais a message saying I'll reach at 7" },
  { id: "files", label: "Open Files", iconName: "Folder", command: "Open Files manager" },
  { id: "vscode", label: "Open VS Code", iconName: "Code2", command: "Open VS Code and start my project" },
  { id: "folder", label: "Create Folder", iconName: "FolderPlus", command: "Create a folder called PLUTO inside my Projects directory" },
  { id: "music", label: "Play Music", iconName: "Music", command: "Play chill focus lofi beats" }
];

export function QuickActions() {
  return (
    <div className="flex items-center justify-center gap-2.5 flex-wrap max-w-[850px] mx-auto my-3 px-4">
      {quickActionsList.map((act) => (
        <QuickAction key={act.id} {...act} />
      ))}
    </div>
  );
}
