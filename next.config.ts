import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  distDir: 'out',
  images: {
    unoptimized: true,
  },
  // PLUTO is a Tauri desktop app: the frontend is a static Next.js export
  // loaded by the native webview - no local server is used at runtime.
};

export default nextConfig;
