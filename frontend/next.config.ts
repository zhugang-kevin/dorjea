import type { NextConfig } from "next";
import path from "path";

const distDir = process.env.NEXT_DIST_DIR;

const nextConfig: NextConfig = {
  ...(distDir ? { distDir } : {}),
  turbopack: {
    root: path.resolve(__dirname),
  },
  experimental: {
    webpackBuildWorker: false,
    workerThreads: false,
    cpus: 1,
    parallelServerCompiles: false,
    parallelServerBuildTraces: false,
    staticGenerationMaxConcurrency: 1,
    staticGenerationMinPagesPerWorker: 1000,
  },
  // Type-check and lint are enforced in scripts/next-build.cjs preflight.
  // Skip Next's internal worker-based validation to avoid sandbox spawn EPERM.
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    const backend =
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.API_BASE_URL ||
      "http://127.0.0.1:8000";

    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
