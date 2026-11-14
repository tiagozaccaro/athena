"use client"

import {
  CircleAlertIcon,
  CircleCheckIcon,
  RotateCwIcon,
  XIcon,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Progress } from "@workspace/ui/components/progress"

import type { Upload } from "@/components/files/use-uploads"
import { formatBytes } from "@/lib/format"

/** Progress of the upload queue, pinned to the bottom of the screen. */
export function UploadsPanel({
  uploads,
  onCancel,
  onRetry,
  onClear,
}: {
  uploads: Upload[]
  onCancel: (id: string) => void
  onRetry: (id: string, overwrite?: boolean) => void
  onClear: () => void
}) {
  if (uploads.length === 0) return null
  const active = uploads.filter(
    (u) => u.status === "queued" || u.status === "uploading"
  ).length
  return (
    <Card
      size="sm"
      className="fixed inset-x-4 bottom-4 z-40 max-h-[50dvh] shadow-lg sm:left-auto sm:w-96"
      role="region"
      aria-label="Uploads"
    >
      <CardHeader>
        <CardTitle>
          {active ? `Uploading ${active} of ${uploads.length}` : "Uploads"}
        </CardTitle>
        <CardAction>
          {active === 0 ? (
            <Button variant="ghost" size="sm" onClick={onClear}>
              Close
            </Button>
          ) : null}
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 overflow-y-auto">
        {uploads.map((u) => {
          const pct = u.file.size
            ? Math.round((u.sent / u.file.size) * 100)
            : 100
          return (
            <div key={u.id} className="flex flex-col gap-1.5 text-sm">
              <div className="flex items-center gap-2">
                {u.status === "done" ? (
                  <CircleCheckIcon className="size-4 shrink-0 text-primary" />
                ) : u.status === "error" ? (
                  <CircleAlertIcon className="size-4 shrink-0 text-destructive" />
                ) : null}
                <span className="min-w-0 flex-1 truncate">{u.file.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  {u.status === "uploading"
                    ? `${pct}%`
                    : u.status === "queued"
                      ? "Waiting"
                      : u.status === "cancelled"
                        ? "Cancelled"
                        : formatBytes(u.file.size)}
                </span>
                {u.status === "queued" || u.status === "uploading" ? (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`Cancel ${u.file.name}`}
                    onClick={() => onCancel(u.id)}
                  >
                    <XIcon />
                  </Button>
                ) : u.status === "error" && !u.conflict ? (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={`Retry ${u.file.name}`}
                    onClick={() => onRetry(u.id)}
                  >
                    <RotateCwIcon />
                  </Button>
                ) : null}
              </div>
              {u.status === "uploading" ? (
                <Progress value={pct} aria-label={`${u.file.name} progress`} />
              ) : null}
              {u.status === "error" ? (
                <div className="flex items-center gap-2">
                  <p className="min-w-0 flex-1 text-xs text-destructive">
                    {u.error}
                  </p>
                  {u.conflict ? (
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => onRetry(u.id, true)}
                    >
                      Replace
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
