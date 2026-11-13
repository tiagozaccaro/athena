"use client"

import * as React from "react"
import { CircleCheckIcon, CircleXIcon } from "lucide-react"

import type { Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Spinner } from "@workspace/ui/components/spinner"

import { LogView } from "@/components/log-view"
import { useEventStream } from "@/hooks/use-event-stream"

type Job = Schemas["JobOut"]

/** Live progress of a background job (GET /api/jobs/{id}/events). */
export function JobDialog({
  job,
  onClose,
  onFinished,
}: {
  job: Job | null
  onClose: () => void
  /** Called once when the job ends, with whether it succeeded. */
  onFinished?: (succeeded: boolean) => void
}) {
  const stream = useEventStream(job ? `/api/jobs/${job.id}/events` : null)
  const status = stream.final?.status
  const reported = React.useRef<string | null>(null)

  React.useEffect(() => {
    if (job && status && reported.current !== job.id) {
      reported.current = job.id
      onFinished?.(status === "succeeded")
    }
  }, [job, status, onFinished])

  const running = !status && stream.phase !== "error"

  return (
    <Dialog open={job !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {running ? (
              <Spinner />
            ) : status === "succeeded" ? (
              <CircleCheckIcon className="text-primary" />
            ) : (
              <CircleXIcon className="text-destructive" />
            )}
            {job?.title}
          </DialogTitle>
          <DialogDescription>
            {running
              ? "Working… You can close this; it keeps running."
              : status === "succeeded"
                ? "Done."
                : (stream.final?.error ??
                  "The connection to the job was lost.")}
          </DialogDescription>
        </DialogHeader>
        <LogView lines={stream.lines} className="h-72" />
        <DialogFooter>
          <Button variant={running ? "outline" : "default"} onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
