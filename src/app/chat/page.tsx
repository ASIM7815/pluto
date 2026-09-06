"use client";

import React, { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { GlassCard } from "@/components/cards/GlassCard";
import { MessageSquare, Send, Mic, Square, Loader2, Volume2, Terminal } from "lucide-react";
import { aiService } from "@/services/ai";
import { usePlutoStore } from "@/store/plutoStore";
import { useVoice } from "@/hooks/useVoice";
import { StopButton } from "@/components/command/StopButton";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  sender: "user" | "pluto";
  text: string;
  timestamp: string;
  actionTaken?: string;
}

const BUSY_STATES = [
  "understanding",
  "thinking",
  "planning",
  "executing",
  "verifying",
  "observing",
  "reasoning",
];

function now(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m-1",
      sender: "pluto",
      text: "Greetings, BOSS. I am PLUTO - your autonomous Linux desktop assistant. Talk or type: I can open apps and websites, search, play videos, manage files and more. What shall we do?",
      timestamp: now()
    }
  ]);
  const [inputVal, setInputVal] = useState("");

  const state = usePlutoStore((s) => s.state);
  const isSpeaking = usePlutoStore((s) => s.isSpeaking);
  const isExecuting = usePlutoStore((s) => s.isExecuting);
  const aiResponse = usePlutoStore((s) => s.aiResponse);
  const errorMessage = usePlutoStore((s) => s.errorMessage);
  const transcript = usePlutoStore((s) => s.transcript);
  const isListening = usePlutoStore((s) => s.isListening);
  const { toggleListening, voiceError } = useVoice();

  const appendedRef = useRef(false);
  const streamRef = useRef<HTMLDivElement | null>(null);

  // Connect to the backend when the chat opens.
  useEffect(() => {
    aiService.connectWebSocket();
  }, []);

  // Show PLUTO's REAL responses (from the agent pipeline) as chat bubbles.
  useEffect(() => {
    if (!aiResponse) {
      appendedRef.current = false; // new command cycle started
      return;
    }
    if (appendedRef.current) return;
    appendedRef.current = true;
    setMessages((prev) => [
      ...prev,
      {
        id: `m-${Date.now()}`,
        sender: "pluto",
        text: aiResponse,
        timestamp: now()
      }
    ]);
  }, [aiResponse]);

  // Keep the latest message in view.
  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isSpeaking, isExecuting]);

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cmd = inputVal.trim();
    if (!cmd) return;

    setMessages((prev) => [
      ...prev,
      { id: `m-${Date.now()}`, sender: "user", text: cmd, timestamp: now() }
    ]);
    setInputVal("");
    void aiService.executeCommand(cmd);
  };

  const handleStop = () => aiService.cancelAction();

  const working = isExecuting || BUSY_STATES.includes(state);

  return (
    <AppShell rightPanel={<ChatRightPanel />}>
      <div className="flex flex-col h-full max-w-4xl mx-auto w-full gap-4">
        {/* Page Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div>
            <h2 className="text-xl font-light text-white tracking-wider flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-[#ff3344]" />
              PLUTO Assistant Chat
            </h2>
            <p className="text-xs text-zinc-400">Natural language conversation &amp; continuous OS automation</p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-[11px] font-mono px-3 py-1 rounded-full border",
                working || isSpeaking
                  ? "bg-[#ff1f2d]/10 border-[#ff1f2d]/30 text-[#ff3344] animate-pulse"
                  : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              )}
            >
              {isSpeaking ? "SPEAKING" : working ? state.toUpperCase() : "LOCAL LLM ACTIVE"}
            </span>
            <StopButton variant="pill" />
          </div>
        </div>

        {/* Message Stream */}
        <div ref={streamRef} className="flex-1 overflow-y-auto space-y-4 pr-2 min-h-[400px]">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.sender === "pluto" && (
                <div className="w-8 h-8 rounded-full bg-[#ff1f2d]/20 border border-[#ff1f2d]/50 flex items-center justify-center text-[#ff3344] shrink-0 font-bold text-xs">
                  P
                </div>
              )}

              <div className={`max-w-[78%] ${msg.sender === "user" ? "items-end" : "items-start"}`}>
                <GlassCard
                  className={`p-4 ${
                    msg.sender === "user"
                      ? "bg-[#ff1f2d]/15 border-[#ff1f2d]/40 text-zinc-100"
                      : "bg-[#0b0b0e] border-white/10 text-zinc-200"
                  }`}
                >
                  <p className="text-sm font-sans leading-relaxed">{msg.text}</p>

                  {msg.actionTaken && (
                    <div className="mt-3 pt-2 border-t border-white/10 flex items-center gap-2 text-xs font-mono text-[#ff3344]">
                      <Terminal className="w-3.5 h-3.5" />
                      <span>Triggered action: &quot;{msg.actionTaken}&quot;</span>
                    </div>
                  )}
                </GlassCard>
                <span className="text-[10px] text-zinc-500 font-mono px-1 mt-1 block">
                  {msg.timestamp}
                </span>
              </div>

              {msg.sender === "user" && (
                <div className="w-8 h-8 rounded-full bg-zinc-800 border border-white/10 flex items-center justify-center text-zinc-300 shrink-0 font-bold text-xs">
                  U
                </div>
              )}
            </div>
          ))}

          {/* Live "PLUTO is working / speaking" bubble with a stop control */}
          {(working || isSpeaking) && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-[#ff1f2d]/20 border border-[#ff1f2d]/50 flex items-center justify-center text-[#ff3344] shrink-0 font-bold text-xs">
                P
              </div>
              <GlassCard className="p-4 bg-[#0b0b0e] border-white/10">
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  {isSpeaking ? (
                    <>
                      <Volume2 className="w-4 h-4 text-[#ff3344] animate-pulse" />
                      <span>Speaking&hellip;</span>
                    </>
                  ) : (
                    <>
                      <Loader2 className="w-4 h-4 text-[#ff3344] animate-spin" />
                      <span className="capitalize">{state}&hellip;</span>
                    </>
                  )}
                  <button
                    type="button"
                    onClick={handleStop}
                    className="ml-2 flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-[#ff1f2d]/15 border border-[#ff1f2d]/50 text-[#ff3344] hover:bg-[#ff1f2d]/30 hover:text-white transition-all cursor-pointer"
                  >
                    <Square className="w-3 h-3 fill-current" /> Stop
                  </button>
                </div>
              </GlassCard>
            </div>
          )}

          {/* Live voice transcript while the mic hears us */}
          {isListening && transcript && (
            <div className="flex gap-3 justify-end">
              <div className="max-w-[78%]">
                <GlassCard className="p-3 bg-[#ff1f2d]/10 border-[#ff1f2d]/30 text-zinc-400 italic">
                  <p className="text-sm">{transcript}</p>
                </GlassCard>
              </div>
            </div>
          )}
        </div>

        {/* Voice problem hint (mic blocked / no mic / speech service down) */}
        {voiceError && (
          <div className="text-[11px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2 flex items-start gap-2">
            <Mic className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>{voiceError}</span>
          </div>
        )}
        {errorMessage && !voiceError && (
          <div className="text-[11px] font-mono text-[#ff3344] bg-[#ff1f2d]/10 border border-[#ff1f2d]/30 rounded-lg px-3 py-2">
            {errorMessage}
          </div>
        )}

        {/* Input Bar: mic, text, stop, send */}
        <form onSubmit={handleSend} className="glass-panel p-2.5 rounded-full border border-white/15 flex items-center gap-2 bg-[#09090c]/90">
          <button
            type="button"
            onClick={toggleListening}
            aria-label={isListening ? "Stop the microphone" : "Speak to PLUTO"}
            className={cn(
              "p-3 rounded-full transition-all cursor-pointer shrink-0",
              isListening
                ? "bg-[#ff1f2d] text-white shadow-[0_0_18px_rgba(255,31,45,0.6)] animate-pulse"
                : "bg-white/5 hover:bg-[#ff1f2d]/20 text-zinc-400 hover:text-[#ff3344] border border-white/10"
            )}
          >
            <Mic className="w-4 h-4" />
          </button>

          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Ask PLUTO anything or request an OS command... (say or type 'stop' to interrupt)"
            className="flex-1 bg-transparent px-4 text-sm text-zinc-100 focus:outline-none placeholder-zinc-500"
          />

          {isSpeaking && (
            <button
              type="button"
              onClick={handleStop}
              aria-label="Stop PLUTO speaking"
              className="p-3 rounded-full bg-[#ff1f2d]/15 hover:bg-[#ff1f2d]/30 border border-[#ff1f2d]/60 text-[#ff3344] hover:text-white transition-all cursor-pointer shrink-0"
            >
              <Square className="w-4 h-4 fill-current" />
            </button>
          )}

          <button
            type="submit"
            className="p-3 rounded-full bg-[#ff1f2d] hover:bg-[#ff3344] text-white shadow-[0_0_15px_rgba(255,31,45,0.4)] transition-all cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </AppShell>
  );
}

function ChatRightPanel() {
  return (
    <>
      <SystemOverview />
      <ActivityPanel />
    </>
  );
}
