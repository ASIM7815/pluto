"use client";

import React from "react";
import { motion } from "framer-motion";
import { AlertCircle, RefreshCw } from "lucide-react";
import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "@/services/ai";
import { GlowButton } from "../common/GlowButton";

interface ErrorCardProps {
  message: string;
}

export function ErrorCard({ message }: ErrorCardProps) {
  const store = usePlutoStore();

  const handleDismiss = () => {
    store.setErrorMessage(null);
    store.resetToIdle();
  };

  const handleRetry = () => {
    const cmd = store.currentCommand;
    store.setErrorMessage(null);
    if (cmd) {
      aiService.executeCommand(cmd);
    } else {
      store.resetToIdle();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="glass-panel p-5 rounded-2xl border border-amber-500/40 max-w-lg w-full bg-[#120a07]/90 shadow-[0_0_35px_rgba(245,158,11,0.2)] my-4"
    >
      <div className="flex items-center gap-3 text-amber-400 mb-2">
        <AlertCircle className="w-5 h-5 text-amber-500" />
        <h4 className="text-sm font-semibold text-zinc-100">
          PLUTO couldn&apos;t complete this
        </h4>
      </div>

      <p className="text-xs text-zinc-300 bg-black/40 p-3 rounded-xl border border-white/5 my-3 font-mono">
        {message}
      </p>

      <div className="flex items-center justify-end gap-3 pt-1">
        <GlowButton variant="ghost" onClick={handleDismiss}>
          Dismiss
        </GlowButton>
        <GlowButton variant="secondary" onClick={handleRetry} className="border-amber-500/30 text-amber-200">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Try Again</span>
        </GlowButton>
      </div>
    </motion.div>
  );
}
