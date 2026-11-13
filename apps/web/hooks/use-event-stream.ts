"use client"

import * as React from "react"

const MAX_LINES = 2000

export type StreamState = {
  lines: string[]
  /** "open" while streaming; "done" after the server's final event; "error" if the stream broke. */
  phase: "connecting" | "open" | "done" | "error"
  /** Payload of the server's final `status` event (jobs), if any. */
  final: { status?: string; error?: string | null } | null
}

/**
 * Follows a Server-Sent Events endpoint that sends `log` events (a JSON string per
 * line) and ends with `status` (jobs) or `end` (log streams). Same-origin, so the
 * session cookie is sent automatically. Pass `null` to disconnect.
 */
export function useEventStream(url: string | null): StreamState {
  const [state, setState] = React.useState<StreamState>({
    lines: [],
    phase: "connecting",
    final: null,
  })

  React.useEffect(() => {
    if (!url) return
    setState({ lines: [], phase: "connecting", final: null })
    const source = new EventSource(url)
    let finished = false

    source.onopen = () => setState((s) => ({ ...s, phase: "open" }))
    source.addEventListener("log", (event) => {
      const line = JSON.parse((event as MessageEvent<string>).data) as string
      setState((s) => {
        const lines =
          s.lines.length >= MAX_LINES ? s.lines.slice(-MAX_LINES + 1) : s.lines
        return { ...s, lines: [...lines, line] }
      })
    })
    const finish = (event: Event) => {
      finished = true
      const data = (event as MessageEvent<string>).data
      setState((s) => ({
        ...s,
        phase: "done",
        final: data ? JSON.parse(data) : null,
      }))
      source.close()
    }
    source.addEventListener("status", finish)
    source.addEventListener("end", finish)
    source.onerror = () => {
      // EventSource reconnects on its own; once the server has finished, stop instead.
      if (finished) return
      source.close()
      setState((s) => ({ ...s, phase: "error" }))
    }
    return () => source.close()
  }, [url])

  return state
}
