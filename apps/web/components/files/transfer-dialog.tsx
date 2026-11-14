"use client"

import * as React from "react"

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
import { Field, FieldDescription, FieldLabel } from "@workspace/ui/components/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"

import {
  isRemote,
  type Location,
  parentOf,
  type Remote,
  sameSource,
  type Source,
} from "@/components/files/file-utils"
import { type Folder, FolderPicker } from "@/components/files/folder-picker"

type OnConflict = NonNullable<Schemas["TransferIn"]["on_conflict"]>
export type TransferRequest = {
  op: "copy" | "move"
  source: Source
  paths: string[]
}
/** Between locations it's the file manager's copy; with a remote on either side,
 * rclone's (/api/cloud/transfer). */
export type TransferStart =
  | { kind: "files"; body: Schemas["TransferIn"] }
  | { kind: "cloud"; body: Schemas["CloudTransferIn"] }

const CONFLICTS: { value: OnConflict; label: string }[] = [
  { value: "rename", label: "Keep both (add a number)" },
  { value: "skip", label: "Skip it" },
  { value: "overwrite", label: "Replace files" },
]

function place(folder: Folder): Schemas["Place"] {
  return isRemote(folder.source)
    ? { remote: folder.source.remote, path: folder.path }
    : { location: folder.source.location, path: folder.path }
}

/** Pick a folder, in any location or remote, to copy or move items into. */
export function TransferDialog({
  request,
  locations,
  remotes,
  onClose,
  onStart,
}: {
  request: TransferRequest | null
  locations: Location[]
  remotes: Remote[]
  onClose: () => void
  onStart: (start: TransferStart) => void
}) {
  const [dest, setDest] = React.useState<Folder>({
    source: { location: 0 },
    path: "",
  })
  const [ok, setOk] = React.useState<boolean | null>(null)
  const [onConflict, setOnConflict] = React.useState<OnConflict>("rename")

  // Start in the folder the items are in.
  React.useEffect(() => {
    if (request) {
      setDest({ source: request.source, path: parentOf(request.paths[0] ?? "") })
    }
  }, [request])

  const verb = request?.op === "move" ? "Move" : "Copy"
  const count = request?.paths.length ?? 0
  const what =
    count === 1 ? request!.paths[0]!.split("/").pop() : `${count} items`
  const selected = new Set(request?.paths ?? [])
  const viaCloud =
    request !== null && (isRemote(request.source) || isRemote(dest.source))

  function start() {
    if (!request) return
    if (!isRemote(request.source) && !isRemote(dest.source)) {
      onStart({
        kind: "files",
        body: {
          op: request.op,
          location: request.source.location,
          paths: request.paths,
          dest_location: dest.source.location,
          dest_path: dest.path,
          on_conflict: onConflict,
        },
      })
      return
    }
    onStart({
      kind: "cloud",
      body: {
        op: request.op,
        source: place({ source: request.source, path: "" }),
        paths: request.paths,
        dest: place(dest),
      },
    })
  }

  return (
    <Dialog open={request !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {verb} {what}
          </DialogTitle>
          <DialogDescription>
            Choose the folder to {verb.toLowerCase()} into.
          </DialogDescription>
        </DialogHeader>
        {request ? (
          <FolderPicker
            id="dest-location"
            label="Location"
            value={dest}
            onChange={setDest}
            onStatus={setOk}
            locations={locations}
            remotes={remotes}
            // A folder can't go into itself.
            blocked={(f) =>
              sameSource(f.source, request.source) && selected.has(f.path)
            }
          />
        ) : null}
        {viaCloud ? (
          <Field>
            <FieldDescription>
              Copied with rclone. A file that&apos;s already there is replaced
              when it differs, and skipped when it&apos;s the same.
            </FieldDescription>
          </Field>
        ) : (
          <Field>
            <FieldLabel htmlFor="on-conflict">If the name is taken</FieldLabel>
            <Select
              items={CONFLICTS}
              value={onConflict}
              onValueChange={(v) => v && setOnConflict(v as OnConflict)}
            >
              <SelectTrigger id="on-conflict" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {CONFLICTS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!request || ok !== true} onClick={start}>
            {verb} here
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
