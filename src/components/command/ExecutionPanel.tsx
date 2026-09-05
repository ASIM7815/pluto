"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Circle, Cpu, AlertTriangle } from "lucide-react";
import { usePlutoStore } from "@/store/plutoStore";
import { GlassCard } from "../cards/GlassCard";

export function ExecutionPanel() {
  const { state, currentTask, executionSteps, isExecuting } = usePlutoStore();

  if (!isExecuting && executionSteps.length === 0) {
    return null;
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 15, scale: 0.95 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="mx-auto w-[90%] max-w-[700px] my-4"
      >
        <GlassCard glow className="bg-[#0a0709]/90 border-[#ff1f2d]/30 p-5">
          {/* Header */}
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/10">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-[#ff1f2d]/20 border border-[#ff1f2d]/40 text-[#ff3344]">
                <Cpu className="w-4 h-4 animate-spin" />
              </span>
              <div>
                <h4 className="text-xs font-mono uppercase tracking-widest text-[#ff3344] font-bold">
                  PLUTO IS WORKING
                </h4>
                <p className="text-[11px] text-zinc-400 font-sans">
                  {currentTask || "Executing AI agent sequence..."}
                </p>
              </div>
            </div>

            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#ff1f2d]/10 text-[#ff3344] border border-[#ff1f2d]/30 uppercase tracking-wider">
              {state}
            </span>
          </div>

          {/* Steps checklist */}
          <div className="space-y-2 font-mono text-xs my-2">
            {executionSteps.map((step) => {
              const isCompleted = step.status === "completed";
              const isCurrent = step.status === "current";
              const isError = step.status === "error";

              return (
                <div
                  key={step.id}
                  className={`flex items-center gap-3 p-2 rounded-lg transition-all duration-200 ${
                    isCurrent
                      ? "bg-[#ff1f2d]/15 border border-[#ff1f2d]/40 text-white shadow-[0_0_12px_rgba(255,31,45,0.2)]"
                      : isCompleted
                      ? "text-zinc-300"
                      : isError
                      ? "bg-red-950/40 border border-red-500/40 text-red-300"
                      : "text-zinc-600 opacity-60"
                  }`}
                >
                  <div className="shrink-0">
                    {isCompleted && (
                      <span className="flex items-center justify-center w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                        <Check className="w-2.5 h-2.5" />
                      </span>
                    )}
                    {isCurrent && (
                      <span className="flex items-center justify-center w-4 h-4 rounded-full bg-[#ff1f2d] text-white animate-pulse">
                        <span className="w-1.5 h-1.5 rounded-full bg-white" />
                      </span>
                    )}
                    {isError && (
                      <span className="flex items-center justify-center w-4 h-4 rounded-full bg-red-500/20 text-red-400 border border-red-500/40">
                        <AlertTriangle className="w-2.5 h-2.5" />
                      </span>
                    )}
                    {!isCompleted && !isCurrent && !isError && (
                      <Circle className="w-3.5 h-3.5 text-zinc-600" />
                    )}
                  </div>

                  <span className="flex-1 truncate">{step.label}</span>
                </div>
              );
            })}
          </div>
        </GlassCard>
      </motion.div>
    </AnimatePresence>
  );
}
