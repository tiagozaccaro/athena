"use client"

import * as React from "react"
import Link from "next/link"
import { RotateCwIcon, SquareTerminalIcon } from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Skeleton } from "@workspace/ui/components/skeleton"

import {
  TerminalSession,
  type SessionState,
} from "@/components/terminal/terminal-session"
import { useTerminalAccess } from "@/components/terminal/use-terminal-access"

export function SessionBadge({ state }: { state: SessionState }) {
  switch (state.phase) {
    case "connecting":
      return <Badge variant="outline">Connecting…</Badge>
    case "open":
      return <Badge variant="secondary">Connected</Badge>
    case "exited":
      return (
        <Badge variant={state.code === 0 ? "outline" : "destructive"}>
          Exited ({state.code})
        </Badge>
      )
    case "closed":
      return <Badge variant="destructive">Disconnected</Badge>
  }
}

export function TerminalUnavailable({
  reason,
  settingsLink,
}: {
  reason: string
  settingsLink?: boolean
}) {
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SquareTerminalIcon />
        </EmptyMedia>
        <EmptyTitle>Terminal unavailable</EmptyTitle>
        <EmptyDescription>{reason}</EmptyDescription>
      </EmptyHeader>
      {settingsLink && (
        <EmptyContent>
          <Button variant="outline" render={<Link href="/settings/system/" />}>
            Open Settings
          </Button>
        </EmptyContent>
      )}
    </Empty>
  )
}

/** The host shell, full height, with a status badge and a New session button. */
export function TerminalView() {
  const access = useTerminalAccess()
  const [session, setSession] = React.useState(0)
  const [state, setState] = React.useState<SessionState>({
    phase: "connecting",
  })

  if (access.state === "loading") return <Skeleton className="h-96 w-full" />
  if (access.state === "unavailable") {
    return (
      <TerminalUnavailable
        reason={access.reason}
        settingsLink={access.settingsLink}
      />
    )
  }

  const ended = state.phase === "exited" || state.phase === "closed"
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <p className="text-sm text-muted-foreground">
            A shell on this server, as the user Athena runs as.
          </p>
          <SessionBadge state={state} />
        </div>
        <Button
          variant={ended ? "default" : "outline"}
          size="sm"
          onClick={() => setSession((n) => n + 1)}
        >
          <RotateCwIcon data-icon="inline-start" />
          New session
        </Button>
      </div>
      {state.phase === "closed" && (
        <p role="alert" className="text-sm text-destructive">
          {state.reason}
        </p>
      )}
      <TerminalSession
        key={session}
        target="host"
        onStateChange={setState}
        className="h-[calc(100svh-var(--header-height)-9rem)] min-h-72"
      />
    </div>
  )
}
