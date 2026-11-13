"use client"

import * as React from "react"

export type ApiState<T> =
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "error"; error: string }

/**
 * Calls an api-client request on mount, and every `refreshMs` if given.
 * The page is a static export, so all data loads in the browser.
 */
export function useApi<T>(
  request: () => Promise<{ data?: T; error?: unknown; response: Response }>,
  refreshMs?: number
): ApiState<T> {
  const [state, setState] = React.useState<ApiState<T>>({ status: "loading" })
  const requestRef = React.useRef(request)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data, response } = await requestRef.current()
        if (cancelled) return
        if (data !== undefined) setState({ status: "ok", data })
        else setState({ status: "error", error: `HTTP ${response.status}` })
      } catch (err) {
        if (!cancelled) {
          setState({ status: "error", error: err instanceof Error ? err.message : String(err) })
        }
      }
    }
    load()
    const timer = refreshMs ? window.setInterval(load, refreshMs) : undefined
    return () => {
      cancelled = true
      if (timer) window.clearInterval(timer)
    }
  }, [refreshMs])

  return state
}
