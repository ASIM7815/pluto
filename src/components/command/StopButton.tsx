"use client";

import React from "react";
import { Square } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "@/services/ai";
import { cn } from "@/lib/utils";

/** States where PLUTO is actively doing something the user may want to stop. */
const BUSY_STATES = [
  "understanding",
  "thinking",
  "planning",
  "executing",
  "verifying",
  "observing",
  "reasoning",
  "speaking",
];

/**
 * Emergency stop for PLUTO's voice + current task. Appears whenever PLUTO is
 * speaking or executing so the user is never trapped listening to an answer
 * they didn't want.
 */
export function StopButton({
  variant = "pill",
  className,
}: {
  variant?: "pill" | "icon";
  className?: string;
}) {
  const isSpeaking = usePlutoStore((s) => s.isSpeaking);
  const isExecuting = usePlutoStore((s) => s.isExecuting);
  const state = usePlutoStore((s) => s.state);

  const busy = isSpeaking || isExecuting || BUSY_STATES.includes(state);
  const label = isSpeaking ? "Stop speaking" : "Stop task";

  return (
    <AnimatePresence>
      {busy && (
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.85 }}
          transition={{ duration: 0.15 }}
          className="flex items-center"
        >
          <button
            type="button"
            onClick={() => aiService.cancelAction()}
            aria-label={label}
            title={`${label} (you can also just say "stop")`}
            className={cn(
              "flex items-center justify-center gap-2 cursor-pointer select-none",
              "bg-[#ff1f2d]/15 hover:bg-[#ff1f2d]/30 border border-[#ff1f2d]/60",
              "text-[#ff3344] hover:text-white transition-all",
              "shadow-[0_0_18px_rgba(255,31,45,0.25)]",
              variant === "pill"
                ? "h-11 px-4 rounded-full text-xs font-semibold tracking-wide"
                : "w-[54px] h-[54px] rounded-full",
              className
            )}
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            {variant === "pill" && <span>STOP</span>}
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
