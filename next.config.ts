import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  distDir: 'out',
  images: {
    unoptimized: true,
  },
  // Note: rewrites are not supported with static export.
  // The desktop launcher uses a local proxy server to forward /api/backend/*.
};

export default nextConfig;
