"use client"

import * as React from "react"
import type { ITheme, Terminal as XTerm } from "@xterm/xterm"
import "@xterm/xterm/css/xterm.css"

import { cn } from "@workspace/ui/lib/utils"

export type TerminalHandle = {
  /**
   * Shows program output: raw bytes (UTF-8 split across chunks is fine) or text.
   * xterm.js renders it as terminal text and never as HTML.
   */
  output: (data: Uint8Array | string) => void
  focus: () => void
  cols: () => number
  rows: () => number
}

export type TerminalProps = {
  ref?: React.Ref<TerminalHandle>
  /** Keystrokes and pastes, to send to the program. */
  onData?: (data: string) => void
  /** The terminal was fitted to a new size. */
  onResize?: (size: { cols: number; rows: number }) => void
  /** xterm.js is loaded, fitted and ready for output. */
  onReady?: (size: { cols: number; rows: number }) => void
  className?: string
  "aria-label"?: string
}

/*
 * ANSI's eight hues have no theme token, so they're fixed per light/dark background,
 * tuned to stay readable on any of the shadcn base colors. Everything else (background,
 * text, cursor, selection, black/white) comes from the active CSS variables.
 */
const HUES_DARK = {
  red: "#f87171",
  green: "#4ade80",
  yellow: "#facc15",
  blue: "#60a5fa",
  magenta: "#e879f9",
  cyan: "#22d3ee",
  brightRed: "#fca5a5",
  brightGreen: "#86efac",
  brightYellow: "#fde047",
  brightBlue: "#93c5fd",
  brightMagenta: "#f0abfc",
  brightCyan: "#67e8f9",
}
const HUES_LIGHT = {
  red: "#b91c1c",
  green: "#15803d",
  yellow: "#a16207",
  blue: "#1d4ed8",
  magenta: "#a21caf",
  cyan: "#0e7490",
  brightRed: "#dc2626",
  brightGreen: "#16a34a",
  brightYellow: "#ca8a04",
  brightBlue: "#2563eb",
  brightMagenta: "#c026d3",
  brightCyan: "#0891b2",
}

/**
 * Opens a link from terminal output, but only http(s), in a new tab with no opener.
 * Program output is untrusted (a file being `cat`, a container's logs), and xterm's
 * default OSC 8 handler would also follow `javascript:` URIs in a same-origin window.
 */
function openLink(_event: MouseEvent, uri: string) {
  let url: URL
  try {
    url = new URL(uri)
  } catch {
    return
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return
  window.open(url.href, "_blank", "noopener,noreferrer")
}

/** Any CSS color (oklch, color-mix…) as rgba(), which xterm.js can parse. */
function toRgba(ctx: CanvasRenderingContext2D, color: string, alpha = 1) {
  ctx.clearRect(0, 0, 1, 1)
  ctx.fillStyle = "#000"
  ctx.fillStyle = color
  ctx.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
  return `rgba(${r}, ${g}, ${b}, ${((a ?? 255) / 255) * alpha})`
}

function readTheme(el: HTMLElement): { theme: ITheme; font: string } {
  const style = getComputedStyle(el)
  const v = (name: string) => style.getPropertyValue(name).trim()
  const canvas = document.createElement("canvas")
  canvas.width = canvas.height = 1
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!
  const c = (name: string, alpha?: number) => toRgba(ctx, v(name), alpha)
  const background = c("--card")
  const [r, g, b] = (background.match(/\d+(\.\d+)?/g) ?? []).map(Number)
  const dark = 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0) < 128
  return {
    font: v("--font-mono") || "ui-monospace, monospace",
    theme: {
      background,
      foreground: c("--card-foreground"),
      cursor: c("--foreground"),
      cursorAccent: background,
      selectionBackground: c("--primary", 0.3),
      black: dark ? c("--muted") : c("--foreground"),
      brightBlack: c("--muted-foreground"),
      white: dark ? c("--foreground") : c("--muted"),
      brightWhite: dark ? c("--foreground") : c("--border"),
      ...(dark ? HUES_DARK : HUES_LIGHT),
    },
  }
}

/**
 * xterm.js themed from the app's CSS variables. It follows the active base color,
 * theme, mono font and light/dark mode, and refits to its box. It only renders; the
 * caller connects it to a program (see the web app's TerminalSession).
 */
function Terminal({
  ref,
  onData,
  onResize,
  onReady,
  className,
  "aria-label": ariaLabel,
}: TerminalProps) {
  const boxRef = React.useRef<HTMLDivElement>(null)
  const termRef = React.useRef<XTerm | null>(null)
  const handlers = React.useRef({ onData, onResize, onReady })
  handlers.current = { onData, onResize, onReady }

  React.useImperativeHandle(
    ref,
    () => ({
      output: (data) => termRef.current?.write(data),
      focus: () => termRef.current?.focus(),
      cols: () => termRef.current?.cols ?? 80,
      rows: () => termRef.current?.rows ?? 24,
    }),
    []
  )

  React.useEffect(() => {
    const box = boxRef.current
    if (!box) return
    let disposed = false
    const cleanups: (() => void)[] = []

    async function start() {
      // xterm.js touches `window` on import, so it loads in the browser only.
      const [{ Terminal: XTermClass }, { FitAddon }, { WebLinksAddon }] =
        await Promise.all([
          import("@xterm/xterm"),
          import("@xterm/addon-fit"),
          import("@xterm/addon-web-links"),
        ])
      await document.fonts.ready // measure cells with the real font
      if (disposed || !box) return

      const { theme, font } = readTheme(box)
      const term = new XTermClass({
        theme,
        fontFamily: font,
        fontSize: 13,
        lineHeight: 1.2,
        cursorBlink: true,
        scrollback: 5000,
        allowProposedApi: false,
        linkHandler: { activate: openLink, allowNonHttpProtocols: false },
      })
      const fit = new FitAddon()
      term.loadAddon(fit)
      term.loadAddon(new WebLinksAddon(openLink))
      term.open(box)
      fit.fit()
      termRef.current = term

      const data = term.onData((d) => handlers.current.onData?.(d))
      const resize = term.onResize((size) => handlers.current.onResize?.(size))
      cleanups.push(
        () => data.dispose(),
        () => resize.dispose()
      )

      const observer = new ResizeObserver(() => {
        if (box.clientWidth > 0 && box.clientHeight > 0) fit.fit()
      })
      observer.observe(box)
      cleanups.push(() => observer.disconnect())

      // Appearance changes are data attributes and classes on <html>.
      const retheme = new MutationObserver(() => {
        const next = readTheme(box)
        term.options.theme = next.theme
        if (term.options.fontFamily !== next.font) {
          term.options.fontFamily = next.font
          document.fonts.ready.then(() => !disposed && fit.fit())
        }
      })
      retheme.observe(document.documentElement, { attributes: true })
      cleanups.push(() => retheme.disconnect())

      cleanups.push(() => term.dispose())
      handlers.current.onReady?.({ cols: term.cols, rows: term.rows })
      term.focus()
    }

    start()
    return () => {
      disposed = true
      termRef.current = null
      for (const cleanup of cleanups.reverse()) cleanup()
    }
  }, [])

  return (
    <div
      data-slot="terminal"
      role="group"
      aria-label={ariaLabel ?? "Terminal"}
      className={cn(
        "relative min-h-0 overflow-hidden rounded-lg border bg-card p-2",
        className
      )}
    >
      <div ref={boxRef} className="size-full" />
    </div>
  )
}

export { Terminal }
