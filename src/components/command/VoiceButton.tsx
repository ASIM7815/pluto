"use client";

import React from "react";
import { Mic, Square } from "lucide-react";
import { motion } from "framer-motion";
import { usePlutoStore } from "@/store/plutoStore";
import { useVoice } from "@/hooks/useVoice";
import { cn } from "@/lib/utils";

export function VoiceButton() {
  const { isListening, toggleListening } = useVoice();
  const isSpeaking = usePlutoStore((s) => s.isSpeaking);
  const isExecuting = usePlutoStore((s) => s.isExecuting);

  // While PLUTO is talking, the mic button becomes a STOP-SPEAKING button so
  // the user always has an obvious way to silence the voice.
  const label = isSpeaking
    ? "Stop PLUTO's voice"
    : isListening
      ? "Stop listening"
      : "Activate PLUTO voice assistant";

  return (
    <div className="relative flex items-center justify-center">
      {/* Outer Pulse Rings when Listening */}
      {isListening && (
        <>
          <motion.div
            initial={{ scale: 0.9, opacity: 0.8 }}
            animate={{ scale: 1.6, opacity: 0 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
            className="absolute inset-0 rounded-full border border-[#ff1f2d] bg-[#ff1f2d]/20 pointer-events-none"
          />
          <motion.div
            initial={{ scale: 0.9, opacity: 0.6 }}
            animate={{ scale: 2.1, opacity: 0 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut", delay: 0.4 }}
            className="absolute inset-0 rounded-full border border-[#ff3344] pointer-events-none"
          />
        </>
      )}

      {/* Main Red Microphone Button */}
      <button
        type="button"
        onClick={toggleListening}
        aria-label={label}
        title={label + ' (or just say "stop")'}
        disabled={isExecuting && !isSpeaking}
        className={cn(
          "relative z-10 w-[54px] h-[54px] rounded-full flex items-center justify-center transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff1f2d]",
          isSpeaking || isListening || isExecuting ? "cursor-pointer" : "cursor-pointer",
          isSpeaking
            ? "bg-white/10 hover:bg-[#ff1f2d] text-white border border-[#ff1f2d]/60 shadow-[0_0_25px_rgba(255,31,45,0.5)]"
            : isListening
              ? "bg-[#ff1f2d] text-white shadow-[0_0_30px_rgba(255,31,45,0.8)] scale-105 cursor-pointer"
              : "bg-red-950/80 hover:bg-[#ff1f2d] text-[#ff3344] hover:text-white border border-[#ff1f2d]/50 hover:border-[#ff1f2d] shadow-[0_0_20px_rgba(255,31,45,0.25)] hover:scale-105 cursor-pointer"
        )}
      >
        {isSpeaking ? (
          <Square className="w-5 h-5 fill-current" />
        ) : (
          <Mic className={cn("w-6 h-6 transition-transform", isListening && "animate-pulse")} />
        )}
      </button>
    </div>
  );
}
