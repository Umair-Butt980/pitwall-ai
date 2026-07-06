import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained .next/standalone bundle (server.js + only the traced
  // node_modules) so the production image doesn't need a full `npm install`.
  output: "standalone",
};

export default nextConfig;
