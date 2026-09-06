"use client";

import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Trash2 } from "lucide-react";
import { ActionPreview } from "@/types";
import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "@/services/ai";
import { GlowButton } from "../common/GlowButton";

interface ConfirmationDialogProps {
  data: ActionPreview;
}

export function ConfirmationDialog({ data }: ConfirmationDialogProps) {
  const store = usePlutoStore();

  const handleCancel = () => {
    store.setConfirmationRequired(null);
    aiService.rejectAction(data.type);
  };

  const handleConfirm = () => {
    store.setConfirmationRequired(null);
    aiService.confirmAction(data.type);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 10 }}
        className="glass-panel p-6 rounded-2xl border border-red-500/40 max-w-md w-full bg-[#0d0708] shadow-[0_0_50px_rgba(255,31,45,0.25)]"
      >
        <div className="flex items-center gap-3 text-red-500 mb-3">
          <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/30">
            <AlertTriangle className="w-6 h-6 text-[#ff3344]" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">Confirm Action</h3>
            <p className="text-xs text-zinc-400">High impact Linux OS operation</p>
          </div>
        </div>

        <div className="my-4 p-3 bg-red-950/20 border border-red-500/20 rounded-xl text-xs text-zinc-300 leading-relaxed">
          {data.content}
          <p className="text-red-400 font-medium mt-2 text-[11px] uppercase tracking-wider">
            ⚠️ This action cannot be undone.
          </p>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <GlowButton variant="ghost" onClick={handleCancel}>
            Cancel
          </GlowButton>
          <GlowButton variant="danger" onClick={handleConfirm}>
            <Trash2 className="w-3.5 h-3.5" />
            <span>Confirm Deletion</span>
          </GlowButton>
        </div>
      </motion.div>
    </div>
  );
}
