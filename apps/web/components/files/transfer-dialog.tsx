"use client"

import * as React from "react"
import { ArrowUpIcon, FolderIcon } from "lucide-react"

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
import { Field, FieldLabel } from "@workspace/ui/components/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"

import { type Location, parentOf } from "@/components/files/file-utils"

type OnConflict = Schemas["TransferIn"]["on_conflict"]
export type TransferRequest = {
  op: "copy" | "move"
  location: number
  paths: string[]
}

const CONFLICTS: { value: NonNullable<OnConflict>; label: string }[] = [
  { value: "rename", label: "Keep both (add a number)" },
  { value: "skip", label: "Skip it" },
  { value: "overwrite", label: "Replace files" },
]

/** Pick a folder, in any location, to copy or move items into. */
export function TransferDialog({
  request,
  locations,
  onClose,
  onStart,
}: {
  request: TransferRequest | null
  locations: Location[]
  onClose: () => void
  onStart: (body: Schemas["TransferIn"]) => void
}) {
  const [dest, setDest] = React.useState<{ location: number; path: string }>({
    location: 0,
    path: "",
  })
  const [folders, setFolders] = React.useState<string[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [onConflict, setOnConflict] =
    React.useState<NonNullable<OnConflict>>("rename")

  // Start in the folder the items are in.
  React.useEffect(() => {
    if (request) {
      setDest({
        location: request.location,
        path: parentOf(request.paths[0] ?? ""),
      })
    }
  }, [request])

  React.useEffect(() => {
    if (!request || !dest.location) return
    let live = true
    setFolders(null)
    setError(null)
    void api
      .GET("/api/files/list", {
        params: { query: { location: dest.location, path: dest.path } },
      })
      .then(({ data, error }) => {
        if (!live) return
        if (data) {
          setFolders(
            data.entries.filter((e) => e.kind === "dir").map((e) => e.name)
          )
        } else {
          setError(errorMessage(error))
          setFolders([])
        }
      })
    return () => {
      live = false
    }
  }, [request, dest])

  const verb = request?.op === "move" ? "Move" : "Copy"
  const count = request?.paths.length ?? 0
  const what =
    count === 1 ? request!.paths[0]!.split("/").pop() : `${count} items`
  const selected = new Set(request?.paths ?? [])
  const items = locations.map((l) => ({ value: String(l.id), label: l.name }))
  const here = locations.find((l) => l.id === dest.location)

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
        <Field>
          <FieldLabel htmlFor="dest-location">Location</FieldLabel>
          <Select
            items={items}
            value={String(dest.location)}
            onValueChange={(v) =>
              v && setDest({ location: Number(v), path: "" })
            }
          >
            <SelectTrigger id="dest-location" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {items.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <div className="rounded-lg border">
          <div className="flex items-center gap-2 border-b px-2 py-1.5">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Up one folder"
              disabled={!dest.path}
              onClick={() => setDest({ ...dest, path: parentOf(dest.path) })}
            >
              <ArrowUpIcon />
            </Button>
            <span className="truncate font-mono text-xs text-muted-foreground">
              {here?.name}/{dest.path}
            </span>
          </div>
          <div className="h-56 overflow-y-auto p-1">
            {folders === null ? (
              <Skeleton className="h-8 w-full" />
            ) : error ? (
              <p className="p-2 text-sm text-destructive">{error}</p>
            ) : folders.length === 0 ? (
              <p className="p-2 text-sm text-muted-foreground">
                No folders here.
              </p>
            ) : (
              folders.map((name) => {
                const path = dest.path ? `${dest.path}/${name}` : name
                // A folder can't go into itself.
                const blocked =
                  dest.location === request?.location && selected.has(path)
                return (
                  <Button
                    key={name}
                    variant="ghost"
                    className="w-full justify-start"
                    disabled={blocked}
                    onClick={() => setDest({ ...dest, path })}
                  >
                    <FolderIcon />
                    <span className="truncate">{name}</span>
                  </Button>
                )
              })
            )}
          </div>
        </div>
        <Field>
          <FieldLabel htmlFor="on-conflict">If the name is taken</FieldLabel>
          <Select
            items={CONFLICTS}
            value={onConflict}
            onValueChange={(v) =>
              v && setOnConflict(v as NonNullable<OnConflict>)
            }
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
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!request || error !== null}
            onClick={() =>
              request &&
              onStart({
                op: request.op,
                location: request.location,
                paths: request.paths,
                dest_location: dest.location,
                dest_path: dest.path,
                on_conflict: onConflict,
              })
            }
          >
            {verb} here
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
