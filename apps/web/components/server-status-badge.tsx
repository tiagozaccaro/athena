"use client"

import { api } from "@workspace/api-client"
import { Badge } from "@workspace/ui/components/badge"

import { useApi } from "@/hooks/use-api"

export function ServerStatusBadge() {
  const health = useApi(() => api.GET("/api/health"), 15_000)

  if (health.status === "loading") {
    return <Badge variant="outline">Connecting…</Badge>
  }
  if (health.status === "error") {
    return <Badge variant="destructive">Server unreachable</Badge>
  }
  return <Badge variant="secondary">Athena {health.data.version}</Badge>
}
