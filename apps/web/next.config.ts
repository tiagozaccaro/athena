import type { NextConfig } from "next"
import { PHASE_DEVELOPMENT_SERVER } from "next/constants"

// Where `athena serve` listens in development (see apps/server/README.md).
const API_DEV_ORIGIN = process.env.ATHENA_API_ORIGIN ?? "http://localhost:8420"

const shared: NextConfig = {
  transpilePackages: ["@workspace/ui", "@workspace/api-client"],
  // Every route becomes <route>/index.html, which FastAPI's StaticFiles serves as-is.
  trailingSlash: true,
  images: { unoptimized: true },
}

export default function config(phase: string): NextConfig {
  // Rewrites are not allowed with a static export, so the /api proxy only exists in
  // `next dev`. In production FastAPI serves the exported UI and the API same-origin.
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      ...shared,
      // Otherwise trailingSlash would 308 every /api call before proxying it.
      skipTrailingSlashRedirect: true,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${API_DEV_ORIGIN}/api/:path*` }]
      },
    }
  }
  return { ...shared, output: "export" }
}
