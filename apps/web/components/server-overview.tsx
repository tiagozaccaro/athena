"use client"

import { CircleAlertIcon } from "lucide-react"

import { api } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Skeleton } from "@workspace/ui/components/skeleton"

import { useApi } from "@/hooks/use-api"

const OS_LABELS = {
  linux: "Linux",
  darwin: "macOS",
  windows: "Windows",
} as const

// M0 dashboard: proves the UI ↔ API round trip. Live stats and app cards come in M4.
export function ServerOverview() {
  const info = useApi(() => api.GET("/api/system/info"))

  if (info.status === "error") {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Can&apos;t reach the Athena server</AlertTitle>
        <AlertDescription>
          {info.error}. In development, start it with{" "}
          <code>uv run athena serve --reload</code> in <code>apps/server</code>.
        </AlertDescription>
      </Alert>
    )
  }

  const rows: [string, string | undefined][] =
    info.status === "ok"
      ? [
          ["Host", info.data.hostname],
          ["Operating system", info.data.os_version],
          ["Platform", `${OS_LABELS[info.data.os]} · ${info.data.arch}`],
          ["Athena", info.data.version],
          ["Python", info.data.python],
        ]
      : [
          ["Host", undefined],
          ["Operating system", undefined],
          ["Platform", undefined],
          ["Athena", undefined],
          ["Python", undefined],
        ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Server</CardTitle>
        <CardDescription>The machine Athena is running on</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="truncate">
                {value ?? <Skeleton className="h-4 w-40" />}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}
