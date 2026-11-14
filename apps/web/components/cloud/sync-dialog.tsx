"use client"

import * as React from "react"
import { ArrowDownIcon, TriangleAlertIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { FieldError } from "@workspace/ui/components/field"
import { Spinner } from "@workspace/ui/components/spinner"

import {
  isRemote,
  type Location,
  type Remote,
} from "@/components/files/file-utils"
import {
  type Folder,
  folderLabel,
  FolderPicker,
} from "@/components/files/folder-picker"

type Job = Schemas["JobOut"]
type Preview = Schemas["SyncPreview"]

function place(folder: Folder): Schemas["Place"] {
  return isRemote(folder.source)
    ? { remote: folder.source.remote, path: folder.path }
    : { location: folder.source.location, path: folder.path }
}

/**
 * Make one folder match another: pick both, preview what changes (and what gets
 * deleted), then run the sync as a job.
 */
export function SyncDialog({
  open,
  locations,
  remotes,
  onClose,
  onStarted,
}: {
  open: boolean
  locations: Location[]
  remotes: Remote[]
  onClose: () => void
  onStarted: (job: Job) => void
}) {
  const [source, setSource] = React.useState<Folder>({
    source: { location: 0 },
    path: "",
  })
  const [dest, setDest] = React.useState<Folder>(source)
  const [preview, setPreview] = React.useState<Preview | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [pending, setPending] = React.useState(false)

  // Each time it opens: from the first location to the first remote. Done on open,
  // not on mount, because the lists load after the page does.
  const firstLocation = locations[0]?.id ?? 0
  const firstRemote = remotes[0]?.name
  React.useEffect(() => {
    if (!open) return
    setSource({ source: { location: firstLocation }, path: "" })
    setDest(
      firstRemote
        ? { source: { remote: firstRemote }, path: "" }
        : { source: { location: firstLocation }, path: "" }
    )
  }, [open, firstLocation, firstRemote])

  // A preview is only good for the folders it was made for.
  React.useEffect(() => {
    setPreview(null)
    setError(null)
  }, [open, source, dest])

  const body = { source: place(source), dest: place(dest) }

  async function check() {
    setPending(true)
    setError(null)
    const { data, error } = await api.POST("/api/cloud/sync/preview", {
      body,
    })
    setPending(false)
    if (data) setPreview(data)
    else setError(errorMessage(error))
  }

  async function run() {
    setPending(true)
    const { data, error } = await api.POST("/api/cloud/sync", { body })
    setPending(false)
    if (data) {
      onStarted(data)
      onClose()
    } else setError(errorMessage(error))
  }

  const destLabel = folderLabel(dest, locations, remotes)

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Sync folders</DialogTitle>
          <DialogDescription>
            Makes the destination match the source: new and changed files are
            copied, and files that aren&apos;t in the source are deleted from
            the destination.
          </DialogDescription>
        </DialogHeader>
        <FolderPicker
          id="sync-source"
          label="From"
          value={source}
          onChange={setSource}
          locations={locations}
          remotes={remotes}
        />
        <ArrowDownIcon className="mx-auto text-muted-foreground" />
        <FolderPicker
          id="sync-dest"
          label="To"
          value={dest}
          onChange={setDest}
          locations={locations}
          remotes={remotes}
        />
        {preview ? (
          preview.delete_count ? (
            <Alert variant="destructive">
              <TriangleAlertIcon />
              <AlertTitle>
                {preview.delete_count} file
                {preview.delete_count === 1 ? "" : "s"} will be deleted from{" "}
                {destLabel}
              </AlertTitle>
              <AlertDescription>
                <ul className="max-h-32 overflow-y-auto font-mono text-xs">
                  {preview.deletes.map((p) => (
                    <li key={p} className="truncate">
                      {p}
                    </li>
                  ))}
                  {preview.delete_count > preview.deletes.length ? (
                    <li>
                      and {preview.delete_count - preview.deletes.length} more
                    </li>
                  ) : null}
                </ul>
                {preview.copy_count} file{preview.copy_count === 1 ? "" : "s"}{" "}
                will be copied.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert>
              <AlertTitle>Nothing will be deleted</AlertTitle>
              <AlertDescription>
                {preview.copy_count
                  ? `${preview.copy_count} file${preview.copy_count === 1 ? "" : "s"} will be copied to ${destLabel}.`
                  : "The folders already match."}
              </AlertDescription>
            </Alert>
          )
        ) : null}
        {error ? <FieldError>{error}</FieldError> : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          {preview ? (
            <Button
              variant={preview.delete_count ? "destructive" : "default"}
              disabled={pending}
              onClick={() => void run()}
            >
              {pending ? <Spinner data-icon="inline-start" /> : null}
              {preview.delete_count
                ? `Sync and delete ${preview.delete_count}`
                : "Sync"}
            </Button>
          ) : (
            <Button disabled={pending} onClick={() => void check()}>
              {pending ? <Spinner data-icon="inline-start" /> : null}
              Check changes
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
