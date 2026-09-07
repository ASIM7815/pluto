"use client";

import React from "react";
import { PlutoState } from "@/types";

interface PlutoOrbProps {
  state: PlutoState;
  size?: number;
  intent?: string | null;
  confidence?: number | null;
  recommendedTools?: string[];
}

interface OrbLook {
  label: string;
  core: string;
  ringA: string;
  ringB: string;
  glow: string;
  animation: string;
  pulse?: boolean;
}

// On-device, state-driven palette. No external assets, no network, no iframe.
function lookForState(state: PlutoState): OrbLook {
  switch (state) {
    case "listening":
      return {
        label: "LISTENING",
        core: "#ff1f2d",
        ringA: "#ff3344",
        ringB: "#ff7a3c",
        glow: "rgba(255,31,45,0.6)",
        animation: "pluto-listen 1.4s ease-in-out infinite",
        pulse: true,
      };
    case "understanding":
    case "thinking":
      return {
        label: state === "understanding" ? "UNDERSTANDING" : "THINKING",
        core: "#8b5cf6",
        ringA: "#a78bfa",
        ringB: "#22d3ee",
        glow: "rgba(139,92,246,0.5)",
        animation: "pluto-swirl 2.2s linear infinite",
      };
    case "planning":
      return {
        label: "PLANNING",
        core: "#eab308",
        ringA: "#facc15",
        ringB: "#f97316",
        glow: "rgba(234,179,8,0.5)",
        animation: "pluto-plan 1.8s linear infinite",
      };
    case "executing":
      return {
        label: "EXECUTING",
        core: "#22d3ee",
        ringA: "#06b6d4",
        ringB: "#3b82f6",
        glow: "rgba(34,211,238,0.6)",
        animation: "pluto-execute 0.7s linear infinite",
        pulse: true,
      };
    case "observing":
    case "reasoning":
      return {
        label: state === "observing" ? "OBSERVING" : "REASONING",
        core: "#14b8a6",
        ringA: "#2dd4bf",
        ringB: "#a3e635",
        glow: "rgba(20,184,166,0.5)",
        animation: "pluto-swirl 2.6s linear infinite",
      };
    case "speaking":
      return {
        label: "SPEAKING",
        core: "#ec4899",
        ringA: "#f472b6",
        ringB: "#fb7185",
        glow: "rgba(236,72,153,0.5)",
        animation: "pluto-listen 1.6s ease-in-out infinite",
        pulse: true,
      };
    case "success":
      return {
        label: "SUCCESS",
        core: "#10b981",
        ringA: "#34d399",
        ringB: "#6ee7b7",
        glow: "rgba(16,185,129,0.55)",
        animation: "pluto-success 1.2s ease-out",
      };
    case "error":
      return {
        label: "ERROR",
        core: "#ef4444",
        ringA: "#f87171",
        ringB: "#fca5a5",
        glow: "rgba(239,68,68,0.6)",
        animation: "pluto-error 0.5s ease-in-out 3",
        pulse: true,
      };
    default:
      return {
        label: "READY",
        core: "#64748b",
        ringA: "#94a3b8",
        ringB: "#cbd5e1",
        glow: "rgba(100,116,139,0.35)",
        animation: "pluto-idle 4s ease-in-out infinite",
      };
  }
}

function confidenceColor(confidence: number | null): string {
  if (confidence == null) return "text-zinc-500";
  if (confidence >= 0.8) return "text-emerald-400";
  if (confidence >= 0.55) return "text-yellow-400";
  return "text-red-400";
}

export function PlutoOrb({
  state,
  size = 420,
  intent = null,
  confidence = null,
  recommendedTools = [],
}: PlutoOrbProps) {
  const look = lookForState(state);
  // Simple rounded confidence %, defaulting to a neutral "—".
  const confidenceLabel =
    confidence == null
      ? "—"
      : `${Math.round(confidence * 100)}%`;

  return (
    <div
      className="relative flex items-center justify-center my-2 select-none"
      data-state={state}
      aria-label={`PLUTO orb - ${look.label}`}
    >
      {/* Background Radial Glow */}
      <div
        className="absolute rounded-full pointer-events-none blur-3xl transition-all duration-700"
        style={{
          width: size * 0.8,
          height: size * 0.8,
          background: `radial-gradient(circle, ${look.glow} 0%, transparent 70%)`,
          opacity: 0.5,
        }}
      />

      {/* Orb core: layered animated SVG rings + core sphere */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 200 200"
        className="relative z-10"
        style={{ filter: `drop-shadow(0 0 22px ${look.glow})` }}
      >
        <defs>
          <radialGradient id="pluto-core" cx="38%" cy="34%" r="70%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="18%" stopColor={look.core} />
            <stop offset="100%" stopColor="#0b0b0f" />
          </radialGradient>
        </defs>

        {/* Outer shimmering ring */}
        <circle
          cx="100" cy="100" r="58" fill="none"
          stroke={look.ringA} strokeWidth="1.4" strokeDasharray="4 7"
          className="origin-center"
          style={{
            animation: look.animation,
            opacity: 0.85,
            transformBox: "fill-box",
            transformOrigin: "center",
          }}
        />
        {/* Middle counter-rotating ring */}
        <circle
          cx="100" cy="100" r="46" fill="none"
          stroke={look.ringB} strokeWidth="0.8" strokeDasharray="2 6"
          className="origin-center"
          style={{
            animationName: look.animation.includes('pluto-') ? look.animation.split(' ')[0] : 'none',
            animationDuration: look.animation.split(' ')[1] || '2s',
            animationTimingFunction: look.animation.includes('ease') ? 'ease-in-out' : 'linear',
            animationIterationCount: 'infinite',
            animationDirection: "reverse",
            opacity: 0.6,
            transformBox: "fill-box",
            transformOrigin: "center",
          }}
        />
        {/* Inner core sphere */}
        <circle cx="100" cy="100" r="34" fill="url(#pluto-core)" />
        {/* Orb highlight */}
        <ellipse cx="87" cy="84" rx="13" ry="9" fill="rgba(255,255,255,0.28)" />
      </svg>

      {/* State label centered over the orb */}
      <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
        <div
          className="flex items-center gap-2 px-3 py-1 rounded-full border font-mono text-[11px] tracking-widest backdrop-blur-md"
          style={{
            borderColor: `${look.ringA}55`,
            color: look.core,
            background: "rgba(0,0,0,0.35)",
          }}
        >
          {look.pulse && (
            <span className="w-2 h-2 rounded-full animate-ping" style={{ background: look.core }} />
          )}
          <span>{look.label}</span>
        </div>
      </div>

      {/* Live brain readout: intent + confidence + planned tools */}
      {(intent || confidence != null || recommendedTools.length > 0) && (
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 z-20 w-full max-w-[85%] flex flex-col items-center gap-1">
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-zinc-400 tracking-widest">INTENT</span>
            <span className="text-white font-medium">{intent ?? "—"}</span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-400 tracking-widest">CONF</span>
            <span className={`font-semibold ${confidenceColor(confidence)}`}>
              {confidenceLabel}
            </span>
          </div>
          {recommendedTools.length > 0 && (
            <div className="flex flex-wrap items-center justify-center gap-1.5">
              {recommendedTools.map((tool) => (
                <span
                  key={tool}
                  className="px-2 py-0.5 rounded-full border border-white/10 bg-black/40 font-mono text-[10px] text-zinc-300"
                >
                  {tool.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
