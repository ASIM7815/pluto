"use client";

import React from "react";
import { motion } from "framer-motion";
import { Mail, MessageCircle, Send, X } from "lucide-react";
import { ActionPreview } from "@/types";
import { usePlutoStore } from "@/store/plutoStore";
import { aiService } from "@/services/ai";
import { GlowButton } from "../common/GlowButton";

interface ActionPreviewCardProps {
  preview: ActionPreview;
}

export function ActionPreviewCard({ preview }: ActionPreviewCardProps) {
  const store = usePlutoStore();

  const handleCancel = () => {
    store.setActionPreview(null);
    aiService.rejectAction(preview.type);
  };

  const handleConfirm = () => {
    aiService.confirmAction(preview.type);
    store.setActionPreview(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.96 }}
      className="glass-panel p-5 rounded-2xl border border-[#ff1f2d]/30 max-w-lg w-full bg-[#0a0a0d]/90 shadow-[0_0_40px_rgba(255,31,45,0.15)] my-4"
    >
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/10">
        <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
          {preview.type === "email" ? (
            <Mail className="w-4 h-4 text-[#ff3344]" />
          ) : (
            <MessageCircle className="w-4 h-4 text-[#ff3344]" />
          )}
          <span>{preview.title}</span>
        </div>
        <button
          onClick={handleCancel}
          className="text-zinc-500 hover:text-white p-1 rounded-md transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-2 text-xs mb-4 font-mono">
        {preview.recipient && (
          <div className="flex items-center gap-2 text-zinc-400">
            <span className="text-zinc-600 uppercase text-[10px]">To:</span>
            <span className="text-zinc-200 bg-white/5 px-2 py-0.5 rounded border border-white/5">
              {preview.recipient}
            </span>
          </div>
        )}
        {preview.subject && (
          <div className="flex items-center gap-2 text-zinc-400">
            <span className="text-zinc-600 uppercase text-[10px]">Subject:</span>
            <span className="text-zinc-200 font-semibold">{preview.subject}</span>
          </div>
        )}
      </div>

      {preview.content && (
        <div className="bg-black/40 p-3 rounded-xl border border-white/5 text-xs text-zinc-300 font-sans leading-relaxed whitespace-pre-wrap mb-4">
          {preview.content}
        </div>
      )}

      <div className="flex items-center justify-end gap-3 pt-2">
        <GlowButton variant="ghost" onClick={handleCancel}>
          Cancel
        </GlowButton>
        <GlowButton variant="primary" onClick={handleConfirm}>
          <Send className="w-3.5 h-3.5" />
          <span>Confirm & Send</span>
        </GlowButton>
      </div>
    </motion.div>
  );
}
