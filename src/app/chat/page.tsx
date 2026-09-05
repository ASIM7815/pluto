"use client";

import React, { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { SystemOverview } from "@/components/system/SystemOverview";
import { ActivityPanel } from "@/components/activity/ActivityPanel";
import { GlassCard } from "@/components/cards/GlassCard";
import { MessageSquare, Send, Terminal } from "lucide-react";
import { aiService } from "@/services/ai";

interface ChatMessage {
  id: string;
  sender: "user" | "pluto";
  text: string;
  timestamp: string;
  actionTaken?: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m-1",
      sender: "pluto",
      text: "Greetings Asim. I am PLUTO, your Linux Desktop AI assistant. How can I assist your OS workflow today?",
      timestamp: "12:00 PM"
    }
  ]);
  const [inputVal, setInputVal] = useState("");

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputVal.trim()) return;

    const userMsg: ChatMessage = {
      id: `m-${Date.now()}`,
      sender: "user",
      text: inputVal,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    };

    setMessages((prev) => [...prev, userMsg]);
    const cmd = inputVal;
    setInputVal("");

    setTimeout(() => {
      const plutoMsg: ChatMessage = {
        id: `m-${Date.now() + 1}`,
        sender: "pluto",
        text: `Understood: "${cmd}". Initiating AI agent execution sequence...`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        actionTaken: cmd
      };
      setMessages((prev) => [...prev, plutoMsg]);
      aiService.executeCommand(cmd);
    }, 600);
  };

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
            <p className="text-xs text-zinc-400">Natural language conversation & continuous OS automation</p>
          </div>
          <span className="text-[11px] font-mono px-3 py-1 rounded-full bg-[#ff1f2d]/10 border border-[#ff1f2d]/30 text-[#ff3344]">
            Local LLM Active
          </span>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-2 min-h-[400px]">
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
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSend} className="glass-panel p-2.5 rounded-full border border-white/15 flex items-center gap-2 bg-[#09090c]/90">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Ask PLUTO anything or request an OS command..."
            className="flex-1 bg-transparent px-4 text-sm text-zinc-100 focus:outline-none placeholder-zinc-500"
          />
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
