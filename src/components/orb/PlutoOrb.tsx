"use client";

import React from "react";
import { PlutoState } from "@/types";

interface PlutoOrbProps {
  state: PlutoState;
  size?: number;
}

export function PlutoOrb({ state, size = 420 }: PlutoOrbProps) {
  return (
    <div className="relative flex items-center justify-center my-2">
      {/* Background Radial Glow */}
      <div
        className="absolute rounded-full pointer-events-none transition-all duration-700 blur-3xl opacity-30"
        style={{
          width: size * 0.8,
          height: size * 0.8,
          background: "radial-gradient(circle, rgba(255,31,45,0.4) 0%, rgba(101,11,16,0.15) 50%, transparent 100%)"
        }}
      />

      {/* Sketchfab 3D Model Embed - A Windy Day */}
      <div
        style={{ width: size, height: size }}
        className="relative z-10 flex items-center justify-center sketchfab-embed-wrapper"
      >
        <iframe
          title="A Windy Day"
          className="w-full h-full rounded-lg"
          style={{ border: "none" }}
          {...({
            frameBorder: "0",
            allowFullScreen: true,
            mozallowfullscreen: "true",
            webkitallowfullscreen: "true",
            allow: "autoplay; fullscreen; xr-spatial-tracking",
            "xr-spatial-tracking": "true",
            "execution-while-out-of-viewport": "true",
            "execution-while-not-rendered": "true",
            "web-share": "true",
            src: "https://sketchfab.com/models/fb78f4cc938144e6902dd5cff354d525/embed?ui_animations=0&ui_stop=0&ui_inspector=0&ui_hint=0&ui_ar=0&ui_help=0&ui_settings=0&ui_vr=0&ui_fullscreen=0&ui_annotations=0&dnt=1&autostart=1&transparent=1&ui_infos=0&ui_controls=1&ui_watermark=0&ui_theme=dark",
          } as any)}
        />
      </div>
    </div>
  );
}
