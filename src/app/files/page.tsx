"use client";

import React from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/cards/GlassCard";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { Folder, FileText, Trash2, FolderPlus } from "lucide-react";
import { aiService } from "@/services/ai";

const sampleFiles = [
  { name: "PLUTO", type: "Directory", size: "128 MB", path: "/home/user/Projects/PLUTO" },
  { name: "desktop-agent.rs", type: "Rust Source", size: "24 KB", path: "/home/user/Projects/PLUTO/src/main.rs" },
  { name: "system_hooks.py", type: "Python Script", size: "8 KB", path: "/home/user/Projects/PLUTO/scripts/hooks.py" },
  { name: "voice_whisper_cache", type: "Cache Directory", size: "1.4 GB", path: "/home/user/.cache/pluto_temp" }
];

export default function FilesPage() {
  const handleCreateFolder = () => {
    aiService.executeCommand("Create a folder called PLUTO inside my Projects directory");
  };

  const handleDeleteCache = () => {
    aiService.executeCommand("Delete cache files in temp directory");
  };

  return (
    <AppShell rightPanel={<FilesRightPanel />}>
      <div className="flex flex-col h-full max-w-5xl mx-auto w-full gap-5">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h2 className="text-xl font-light text-white tracking-wider flex items-center gap-2">
              <Folder className="w-5 h-5 text-[#ff3344]" />
              File System Inspector
            </h2>
            <p className="text-xs text-zinc-400">Explore Linux directories & execute AI file operations</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCreateFolder}
              className="px-3 py-1.5 rounded-lg bg-[#ff1f2d]/20 hover:bg-[#ff1f2d]/30 text-[#ff3344] border border-[#ff1f2d]/40 text-xs font-mono flex items-center gap-2 transition-all cursor-pointer"
            >
              <FolderPlus className="w-4 h-4" />
              <span>Create Folder</span>
            </button>
            <button
              onClick={handleDeleteCache}
              className="px-3 py-1.5 rounded-lg bg-red-950/40 hover:bg-red-900/60 text-red-300 border border-red-500/30 text-xs font-mono flex items-center gap-2 transition-all cursor-pointer"
            >
              <Trash2 className="w-4 h-4" />
              <span>Clean Cache</span>
            </button>
          </div>
        </div>

        <div className="space-y-3">
          {sampleFiles.map((file, idx) => (
            <GlassCard key={idx} className="flex items-center justify-between p-4 bg-[#09090c]">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">
                  {file.type === "Directory" || file.type === "Cache Directory" ? (
                    <Folder className="w-5 h-5 text-[#ff3344]" />
                  ) : (
                    <FileText className="w-5 h-5 text-amber-400" />
                  )}
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-zinc-100">{file.name}</h4>
                  <p className="text-[11px] text-zinc-500 font-mono">{file.path}</p>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono text-zinc-400">
                <span>{file.type}</span>
                <span className="px-2 py-0.5 rounded bg-white/5 border border-white/5 text-zinc-300">
                  {file.size}
                </span>
              </div>
            </GlassCard>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function FilesRightPanel() {
  return (
    <>
      <SystemOverview />
      <ActivityPanel />
    </>
  );
}
