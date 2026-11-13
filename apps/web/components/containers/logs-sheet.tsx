"use client"

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"

import { LogView } from "@/components/log-view"
import { useEventStream } from "@/hooks/use-event-stream"

/** Follows a container's logs live while open. */
export function LogsSheet({
  container,
  onClose,
}: {
  container: { id: string; name: string } | null
  onClose: () => void
}) {
  const stream = useEventStream(
    container
      ? `/api/containers/${encodeURIComponent(container.id)}/logs/stream?tail=300`
      : null
  )
  const state =
    stream.phase === "open"
      ? "Following new output"
      : stream.phase === "done"
        ? "The container stopped"
        : stream.phase === "error"
          ? "Disconnected"
          : "Connecting…"

  return (
    <Sheet
      open={container !== null}
      onOpenChange={(open) => !open && onClose()}
    >
      <SheetContent side="right" className="w-full gap-0 sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>Logs · {container?.name}</SheetTitle>
          <SheetDescription>{state}</SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1 px-4 pb-4">
          <LogView
            lines={stream.lines}
            className="h-full"
            placeholder="No log output."
          />
        </div>
      </SheetContent>
    </Sheet>
  )
}
