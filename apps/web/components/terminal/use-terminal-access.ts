"use client"

import { api } from "@workspace/api-client"

import { useAuth } from "@/components/auth-provider"
import { useCapability } from "@/components/capabilities-provider"
import { useApi } from "@/hooks/use-api"

export type TerminalAccess =
  | { state: "loading" }
  | { state: "ready" }
  | { state: "unavailable"; reason: string; settingsLink?: boolean }

/**
 * Whether this user can open a terminal here: the host supports it, they're an admin,
 * and it's on in Settings → System. The server checks all of this again.
 */
export function useTerminalAccess(): TerminalAccess {
  const { user } = useAuth()
  const capability = useCapability("terminal.host")
  const settings = useApi(() => api.GET("/api/settings/system"))

  if (!capability || settings.status === "loading") return { state: "loading" }
  if (!capability.available) {
    return {
      state: "unavailable",
      reason: capability.detail ?? "This host has no terminal support.",
    }
  }
  if (!user.is_admin) {
    return { state: "unavailable", reason: "Only admins can open a terminal." }
  }
  if (settings.status === "ok" && !settings.data.terminal_enabled) {
    return {
      state: "unavailable",
      reason: "The terminal is turned off in Settings → System.",
      settingsLink: true,
    }
  }
  return { state: "ready" }
}
