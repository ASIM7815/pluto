"use client";

import React, { useState, useEffect } from "react";
import { Plus, ArrowRight, Keyboard, MicOff } from "lucide-react";
import { VoiceButton } from "./VoiceButton";
import { VoiceWaveform } from "./VoiceWaveform";
import { StopButton } from "./StopButton";
import { usePlutoStore } from "@/store/plutoStore";
import { useVoice } from "@/hooks/useVoice";
import { aiService } from "@/services/ai";
import { cn } from "@/lib/utils";

export function CommandBar() {
  const [inputVal, setInputVal] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const store = usePlutoStore();
  const { isListening, transcript, voiceError } = useVoice();

  // Sync transcript to input field when voice is active
  useEffect(() => {
    if (isListening && transcript) {
      setInputVal(transcript);
    }
  }, [isListening, transcript]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = inputVal.trim();
    if (!query) return;

    store.setCommand(query);
    aiService.executeCommand(query);
    setInputVal("");
  };

  return (
    <div className="relative">
      {voiceError && (
        <div className="mx-auto w-[90%] max-w-[900px] mb-2 flex items-center gap-2 text-[11px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-1.5">
          <MicOff className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate">{voiceError}</span>
        </div>
      )}
    <form
      onSubmit={handleSubmit}
      className={cn(
        "relative mx-auto w-[90%] max-w-[900px] h-[74px] rounded-[40px] px-5 flex items-center justify-between gap-3 transition-all duration-300 backdrop-blur-2xl z-20",
        "bg-[#0b0b0f]/85 border",
        isFocused || isListening
          ? "border-[#ff1f2d] shadow-[0_0_35px_rgba(255,31,45,0.35)]"
          : "border-white/10 hover:border-white/20 shadow-[0_20px_50px_rgba(0,0,0,0.6)]"
      )}
    >
      {/* Plus Action Icon */}
      <button
        type="button"
        className="p-2.5 rounded-full bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white border border-white/10 transition-colors flex items-center justify-center shrink-0"
        title="Quick attach context or file"
      >
        <Plus className="w-5 h-5" />
      </button>

      {/* Controlled Input Field or Voice Waveform */}
      <div className="flex-1 flex items-center gap-3 min-w-0">
        {isListening ? (
          <div className="flex items-center gap-3 w-full">
            <VoiceWaveform />
            <span className="text-sm font-mono text-[#ff3344] animate-pulse truncate">
              {inputVal || "● Listening..."}
            </span>
          </div>
        ) : (
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="Type a command or ask anything..."
            className="w-full bg-transparent text-sm sm:text-base font-sans text-zinc-100 placeholder-zinc-500 focus:outline-none tracking-wide"
          />
        )}
      </div>

      {/* Right Controls: Keyboard Hint, Voice Button, Submit Arrow */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="hidden sm:flex items-center gap-1 text-[11px] text-zinc-500 font-mono px-2.5 py-1 rounded-full bg-white/5 border border-white/5">
          <Keyboard className="w-3.5 h-3.5 text-zinc-400" />
          <span>Ctrl + Space</span>
        </div>

        <StopButton />

        <VoiceButton />

        <button
          type="submit"
          disabled={!inputVal.trim()}
          className={cn(
            "p-2.5 rounded-full transition-all duration-200 flex items-center justify-center shrink-0",
            inputVal.trim()
              ? "bg-[#ff1f2d] text-white hover:bg-[#ff3344] shadow-[0_0_15px_rgba(255,31,45,0.5)] cursor-pointer scale-100"
              : "bg-white/5 text-zinc-600 border border-white/5 cursor-not-allowed scale-95"
          )}
        >
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </form>
    </div>
  );
}
