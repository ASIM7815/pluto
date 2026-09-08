"use client";

import React from "react";
import { motion } from "framer-motion";
import { usePlutoStore } from "@/store/plutoStore";

/** Animated mic meter. Bars are driven by the live audio level (0..1) that
 *  the Rust capture loop streams back - they dance with the user's voice. */
export function VoiceWaveform() {
  const level = usePlutoStore((s) => s.audioLevel);
  // Even "silent" listening keeps a gentle idle motion so the state is clear.
  const energy = 0.25 + Math.min(0.75, level) * 3;
  const bars = [0.5, 1, 0.65, 1.25, 0.8, 1.4, 0.6, 1.15, 0.45, 1, 0.7, 1.3, 0.55, 1.1, 0.85];

  return (
    <div className="flex items-center gap-1 h-8 px-2">
      {bars.map((factor, idx) => {
        const base = 6 + factor * 10 * Math.min(2, energy);
        return (
          <motion.span
            key={idx}
            className="w-1 bg-[#ff3344] rounded-full shadow-[0_0_8px_rgba(255,51,68,0.8)]"
            animate={{ height: [base * 0.35, base, base * 0.5, base * 0.9, base * 0.35] }}
            transition={{
              duration: 0.55 + (idx % 4) * 0.09,
              repeat: Infinity,
              repeatType: "mirror",
              delay: idx * 0.05
            }}
          />
        );
      })}
    </div>
  );
}
