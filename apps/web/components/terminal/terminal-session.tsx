"use client"

import * as React from "react"

import { getCsrfToken } from "@workspace/api-client"
import {
  Terminal,
  type TerminalHandle,
} from "@workspace/ui/components/athena/terminal"

export type SessionState =
  | { phase: "connecting" }
  | { phase: "open" }
  | { phase: "exited"; code: number }
  | { phase: "closed"; reason: string }

/** Why the server closed the socket, in words (codes from athena/api/terminal.py). */
function closeReason(event: CloseEvent): string {
  // Plain text only: no escape codes from the close frame reach the terminal.
  // eslint-disable-next-line no-control-regex
  const reason = event.reason.replace(/[\u0000-\u001f\u007f-\u009f]/g, "")
  if (reason) return reason
  if (event.code === 1006) return "The connection to Athena was lost"
  return `Disconnected (code ${event.code})`
}

/**
 * A terminal connected to `/api/terminal/ws`: the host shell (`target="host"`) or a
 * shell in a container (`target="container:<id>"`). Remount it (change `key`) for a
 * new session.
 */
export function TerminalSession({
  target,
  onStateChange,
  className,
}: {
  target: string
  onStateChange?: (state: SessionState) => void
  className?: string
}) {
  const termRef = React.useRef<TerminalHandle>(null)
  const wsRef = React.useRef<WebSocket | null>(null)
  const notify = React.useRef(onStateChange)
  notify.current = onStateChange

  React.useEffect(() => () => wsRef.current?.close(1000), [])

  const send = React.useCallback((message: object) => {
    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message))
  }, [])

  const connect = React.useCallback(
    ({ cols, rows }: { cols: number; rows: number }) => {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws"
      const url = `${scheme}://${window.location.host}/api/terminal/ws?target=${encodeURIComponent(target)}`
      const ws = new WebSocket(url)
      ws.binaryType = "arraybuffer"
      wsRef.current = ws
      let exited = false
      notify.current?.({ phase: "connecting" })

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            type: "auth",
            csrf: getCsrfToken() ?? "",
            cols,
            rows,
          })
        )
      }
      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          termRef.current?.output(new Uint8Array(event.data))
          return
        }
        const message = JSON.parse(String(event.data)) as
          { type: "ready" } | { type: "exit"; code: number }
        if (message.type === "ready") {
          notify.current?.({ phase: "open" })
          termRef.current?.focus()
        } else if (message.type === "exit") {
          exited = true
          // Only ever an integer, so a malformed message can't inject escape codes.
          const code = Number.isInteger(message.code)
            ? Number(message.code)
            : -1
          termRef.current?.output(
            `\r\n\x1b[2m[Exited with code ${code}]\x1b[0m\r\n`
          )
          notify.current?.({ phase: "exited", code })
        }
      }
      ws.onclose = (event) => {
        if (wsRef.current !== ws || exited) return
        const reason = closeReason(event)
        termRef.current?.output(`\r\n\x1b[2m[${reason}]\x1b[0m\r\n`)
        notify.current?.({ phase: "closed", reason })
      }
    },
    [target]
  )

  return (
    <Terminal
      ref={termRef}
      className={className}
      aria-label={target === "host" ? "Host terminal" : "Container shell"}
      onReady={connect}
      onData={(data) => send({ type: "input", data })}
      onResize={({ cols, rows }) => send({ type: "resize", cols, rows })}
    />
  )
}
