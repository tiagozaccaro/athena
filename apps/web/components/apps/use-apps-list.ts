"use client"

import * as React from "react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"

export type AppOut = Schemas["AppOut"]

const REFRESH_MS = 10_000

/**
 * The app list from `/api/apps`, refreshed every 10 s. Statuses come from container
 * labels, so changes made outside Athena (or by a finished job) show up on their own;
 * call `load()` to refresh right away.
 */
export function useAppsList() {
  const [apps, setApps] = React.useState<AppOut[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    const { data, error: err } = await api.GET("/api/apps")
    if (data) {
      setApps(data)
      setError(null)
    } else setError(errorMessage(err, "Couldn't list apps"))
  }, [])

  React.useEffect(() => {
    void load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [load])

  return { apps, error, load }
}
