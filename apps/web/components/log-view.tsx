"use client"

import * as React from "react"

import { ScrollArea } from "@workspace/ui/components/scroll-area"
import { cn } from "@workspace/ui/lib/utils"

/** Monospace output that keeps the newest line in view while streaming. */
export function LogView({
  lines,
  placeholder = "No output yet.",
  className,
}: {
  lines: string[]
  placeholder?: string
  className?: string
}) {
  const end = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    end.current?.scrollIntoView({ block: "end" })
  }, [lines.length])

  return (
    <ScrollArea className={cn("rounded-lg border bg-muted/50", className)}>
      <pre className="p-3 font-mono text-xs leading-relaxed break-all whitespace-pre-wrap">
        {lines.length ? (
          lines.join("\n")
        ) : (
          <span className="text-muted-foreground">{placeholder}</span>
        )}
        <div ref={end} />
      </pre>
    </ScrollArea>
  )
}
