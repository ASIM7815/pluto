"use client";

import React from "react";

interface MetricRingProps {
  label: string;
  value: number; // 0 - 100
  sublabel?: string;
  size?: number;
  strokeWidth?: number;
  color?: string;
}

export function MetricRing({
  label,
  value,
  sublabel,
  size = 76,
  strokeWidth = 6,
  color = "#ff1f2d"
}: MetricRingProps) {
  // Ensure value is a valid number between 0-100
  const safeValue = typeof value === 'number' && !isNaN(value) ? Math.min(Math.max(value, 0), 100) : 0;
  
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (safeValue / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center group">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background Ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {/* Progress Ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            className="transition-all duration-700 ease-out"
            style={{
              filter: `drop-shadow(0 0 6px ${color})`
            }}
          />
        </svg>
        {/* Center Percentage */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-sm font-bold text-zinc-100 group-hover:text-white font-mono tracking-tight">
            {safeValue}%
          </span>
        </div>
      </div>
      <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-widest mt-2">
        {label}
      </span>
      {sublabel && (
        <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
          {sublabel}
        </span>
      )}
    </div>
  );
}
