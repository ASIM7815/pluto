import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy all /api/backend/* calls (REST + WebSocket) to the FastAPI backend.
  // This keeps the frontend using relative URLs so it works from any host
  // (including the sandbox preview host) without hardcoding 127.0.0.1:8765.
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: "http://127.0.0.1:8765/api/:path*",
      },
    ];
  },
};

export default nextConfig;
