"use client"

import * as React from "react"

import { api, type Schemas } from "@workspace/api-client"

export type Capability = Schemas["Capability"]
export type CapabilityManifest = Schemas["CapabilityManifest"]

type CapabilitiesState = {
  manifest: CapabilityManifest | null
  error: string | null
  refreshing: boolean
  /** Re-run detection on the server (e.g. after installing a runtime). */
  refresh: () => Promise<void>
}

const CapabilitiesContext = React.createContext<CapabilitiesState | null>(null)

/**
 * Loads the host's capability manifest once for the whole app shell.
 * Everything host-specific in the UI is gated on it (docs/mvp-design.md §3).
 */
export function CapabilitiesProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [manifest, setManifest] = React.useState<CapabilityManifest | null>(
    null
  )
  const [error, setError] = React.useState<string | null>(null)
  const [refreshing, setRefreshing] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    api
      .GET("/api/system/capabilities")
      .then(({ data, response }) => {
        if (cancelled) return
        if (data) setManifest(data)
        else setError(`HTTP ${response.status}`)
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const refresh = React.useCallback(async () => {
    setRefreshing(true)
    try {
      const { data, response } = await api.POST(
        "/api/system/capabilities/refresh"
      )
      if (data) {
        setManifest(data)
        setError(null)
      } else {
        setError(`HTTP ${response.status}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefreshing(false)
    }
  }, [])

  const value = React.useMemo(
    () => ({ manifest, error, refreshing, refresh }),
    [manifest, error, refreshing, refresh]
  )
  return <CapabilitiesContext value={value}>{children}</CapabilitiesContext>
}

export function useCapabilities(): CapabilitiesState {
  const ctx = React.useContext(CapabilitiesContext)
  if (!ctx)
    throw new Error(
      "useCapabilities must be used inside <CapabilitiesProvider>"
    )
  return ctx
}

/** The capability with this id, or undefined while loading or if the host doesn't report it. */
export function useCapability(id: string): Capability | undefined {
  return useCapabilities().manifest?.capabilities.find((c) => c.id === id)
}

/**
 * Whether a nav item shows on this host. Items without a capability always show.
 * `showWhenUnavailable` items also show when stopped/missing, but never when the
 * capability isn't reported at all or is unsupported here.
 */
export function isAllowed(
  manifest: CapabilityManifest | null,
  capability?: string,
  showWhenUnavailable = false
): boolean {
  if (!capability) return true
  const cap = manifest?.capabilities.find((c) => c.id === capability)
  if (!cap) return false
  if (cap.available) return true
  return showWhenUnavailable && cap.status !== "unsupported"
}
