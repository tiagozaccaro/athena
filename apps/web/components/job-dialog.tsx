"use client"

import * as React from "react"
import { CircleCheckIcon, CircleXIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Progress } from "@workspace/ui/components/progress"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import { LogView } from "@/components/log-view"
import { useEventStream } from "@/hooks/use-event-stream"

type Job = Schemas["JobOut"]

/** Live progress of a background job (GET /api/jobs/{id}/events), with a progress bar
 * and a Cancel button for jobs that offer them. */
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
  const progress = stream.progress ?? job?.progress ?? null
  const [cancelling, setCancelling] = React.useState(false)
  React.useEffect(() => setCancelling(false), [job?.id])

  async function cancel() {
    if (!job) return
    setCancelling(true)
    const { error } = await api.POST("/api/jobs/{job_id}/cancel", {
      params: { path: { job_id: job.id } },
    })
    if (error) {
      setCancelling(false)
      toast.add({
        type: "error",
        title: "Couldn't stop it",
        description: errorMessage(error),
      })
    }
  }

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
        {progress ? (
          <div className="flex flex-col gap-2">
            {progress.fraction != null ? (
              <Progress
                value={Math.round(progress.fraction * 100)}
                aria-label="Progress"
              />
            ) : null}
            <p className="text-sm text-muted-foreground tabular-nums">
              {progress.text}
              {/* rclone counts bytes once read; the remote may still be taking them. */}
              {running && (progress.fraction ?? 0) >= 1 ? " · finishing…" : null}
            </p>
          </div>
        ) : null}
        <LogView lines={stream.lines} className="h-72" />
        <DialogFooter>
          {running && job?.cancellable ? (
            <Button
              variant="destructive"
              disabled={cancelling}
              onClick={() => void cancel()}
            >
              {cancelling ? <Spinner data-icon="inline-start" /> : null}
              Cancel job
            </Button>
          ) : null}
          <Button variant={running ? "outline" : "default"} onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
