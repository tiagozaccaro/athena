"use client"

import * as React from "react"

import { api, errorMessage } from "@workspace/api-client"

import { useCapabilities } from "@/components/capabilities-provider"
import type { Remote } from "@/components/files/file-utils"

export type RemotesState = {
  /** Empty when rclone isn't ready on this host; null while loading. */
  remotes: Remote[] | null
  error: string | null
  ready: boolean
  reload: () => Promise<void>
}

/** The cloud remotes, when the host has rclone (capability `cloud.rclone`). */
export function useRemotes(): RemotesState {
  const { manifest } = useCapabilities()
  const ready =
    manifest?.capabilities.find((c) => c.id === "cloud.rclone")?.status ===
    "ready"
  const [remotes, setRemotes] = React.useState<Remote[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const reload = React.useCallback(async () => {
    if (!ready) {
      setRemotes([])
      return
    }
    const { data, error } = await api.GET("/api/cloud/remotes")
    setRemotes(data ?? [])
    setError(data ? null : errorMessage(error))
  }, [ready])

  React.useEffect(() => {
    // Wait for the capability manifest before deciding there are none.
    if (manifest) void reload()
  }, [manifest, reload])

  return { remotes, error, ready, reload }
}
