"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/cards/GlassCard";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { Settings, Shield, Mic, Key, Check } from "lucide-react";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);
  const [voiceModel, setVoiceModel] = useState("local-whisper-v3");
  const [llmProvider, setLlmProvider] = useState("local-ollama");

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <AppShell rightPanel={<SettingsRightPanel />}>
      <div className="flex flex-col h-full max-w-4xl mx-auto w-full gap-5">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h2 className="text-xl font-light text-white tracking-wider flex items-center gap-2">
              <Settings className="w-5 h-5 text-[#ff3344]" />
              PLUTO Assistant Settings
            </h2>
            <p className="text-xs text-zinc-400">Configure LLM providers, voice recognition, and Tauri bridge permissions</p>
          </div>

          <button
            onClick={handleSave}
            className="px-4 py-1.5 rounded-xl bg-[#ff1f2d] hover:bg-[#ff3344] text-white text-xs font-mono flex items-center gap-2 transition-all cursor-pointer shadow-[0_0_15px_rgba(255,31,45,0.4)]"
          >
            {saved ? <Check className="w-4 h-4" /> : null}
            <span>{saved ? "Saved" : "Save Changes"}</span>
          </button>
        </div>

        <div className="space-y-4">
          <GlassCard className="p-5 bg-[#09090d] space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Mic className="w-4 h-4 text-[#ff3344]" />
              Voice Speech Recognition Engine
            </h3>
            <div className="space-y-2">
              <label className="text-xs text-zinc-400 font-mono block">STT Model Selection</label>
              <select
                value={voiceModel}
                onChange={(e) => setVoiceModel(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-black/60 border border-white/10 text-xs text-zinc-200 focus:outline-none focus:border-[#ff1f2d]"
              >
                <option value="local-whisper-v3">PLUTO Native Microphone + whisper.cpp (local, optional external model)</option>
                <option value="none">No STT engine installed (type commands)</option>
              </select>
              <p className="text-[10px] text-zinc-500 font-mono">
                Microphone capture is native (no Web Speech API, no cloud). For voice commands, install
                whisper.cpp and put a small ggml model in ~/.cache/pluto/ - PLUTO keeps working without it.
              </p>
            </div>
          </GlassCard>

          <GlassCard className="p-5 bg-[#09090d] space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-[#ff3344]" />
              Language Model & Reasoning Provider
            </h3>
            <div className="space-y-2">
              <label className="text-xs text-zinc-400 font-mono block">Primary LLM Provider</label>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-black/60 border border-white/10 text-xs text-zinc-200 focus:outline-none focus:border-[#ff1f2d]"
              >
                <option value="pluto-pattern">PLUTO Pattern Intelligence (on-device, deterministic)</option>
                <option value="local-ollama">Local Ollama (optional, if you install it)</option>
              </select>
              <p className="text-[10px] text-zinc-500 font-mono">
                PLUTO understands desktop commands fully on-device - no API keys, no cloud services required.
              </p>
            </div>
          </GlassCard>

          <GlassCard className="p-5 bg-[#09090d] space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              Tauri OS Security & Execution Sandboxing
            </h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              PLUTO executes desktop commands through strict Tauri system IPC channels. Arbitrary shell command execution is prohibited by default.
            </p>
            <div className="pt-2 flex items-center gap-2 text-xs font-mono text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              <span>Safety Sandboxing Active</span>
            </div>
          </GlassCard>
        </div>
      </div>
    </AppShell>
  );
}

function SettingsRightPanel() {
  return (
    <>
      <SystemOverview />
      <ActivityPanel />
    </>
  );
}
