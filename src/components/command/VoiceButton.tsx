"use client";

import React from "react";
import { Mic } from "lucide-react";
import { motion } from "framer-motion";
import { useVoice } from "@/hooks/useVoice";
import { cn } from "@/lib/utils";

export function VoiceButton() {
  const { isListening, toggleListening } = useVoice();

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
        aria-label="Activate PLUTO voice assistant"
        className={cn(
          "relative z-10 w-[54px] h-[54px] rounded-full flex items-center justify-center transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff1f2d] cursor-pointer",
          isListening
            ? "bg-[#ff1f2d] text-white shadow-[0_0_30px_rgba(255,31,45,0.8)] scale-105"
            : "bg-red-950/80 hover:bg-[#ff1f2d] text-[#ff3344] hover:text-white border border-[#ff1f2d]/50 hover:border-[#ff1f2d] shadow-[0_0_20px_rgba(255,31,45,0.25)] hover:scale-105"
        )}
      >
        <Mic className={cn("w-6 h-6 transition-transform", isListening && "animate-pulse")} />
      </button>
    </div>
  );
}
