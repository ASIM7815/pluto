"use client";

import React from "react";
import { motion } from "framer-motion";

export function VoiceWaveform() {
  const bars = [16, 28, 12, 32, 20, 24, 10, 26, 18];

  return (
    <div className="flex items-center gap-1 h-8 px-2">
      {bars.map((height, idx) => (
        <motion.span
          key={idx}
          className="w-1 bg-[#ff3344] rounded-full shadow-[0_0_8px_rgba(255,51,68,0.8)]"
          animate={{
            height: [8, height, 6, height * 0.8, 8]
          }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            repeatType: "mirror",
            delay: idx * 0.08
          }}
        />
      ))}
    </div>
  );
}
