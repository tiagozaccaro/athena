"use client"

import * as React from "react"
import { ArrowUpIcon, CloudIcon, FolderIcon, HardDriveIcon } from "lucide-react"

import { api, errorMessage } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import { Field, FieldLabel } from "@workspace/ui/components/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"

import {
  isRemote,
  joinPath,
  type Location,
  parentOf,
  type Remote,
  type Source,
  sourceFromKey,
  sourceKey,
} from "@/components/files/file-utils"

export type Folder = { source: Source; path: string }

/** Lists the folders in `folder`, from a location or a remote. */
async function listFolders(
  folder: Folder
): Promise<{ names: string[] } | { error: string }> {
  const { data, error } = isRemote(folder.source)
    ? await api.GET("/api/cloud/files/list", {
        params: { query: { remote: folder.source.remote, path: folder.path } },
      })
    : await api.GET("/api/files/list", {
        params: {
          query: { location: folder.source.location, path: folder.path },
        },
      })
  if (!data) return { error: errorMessage(error) }
  return {
    names: data.entries.filter((e) => e.kind === "dir").map((e) => e.name),
  }
}

/** A name for a folder, like "Home/photos" or "gdrive:/photos". */
export function folderLabel(
  folder: Folder,
  locations: Location[],
  remotes: Remote[] = []
): string {
  if (isRemote(folder.source)) {
    const name =
      remotes.find((r) => isRemote(folder.source) && r.name === folder.source.remote)
        ?.name ?? folder.source.remote
    return `${name}:/${folder.path}`
  }
  const loc = locations.find(
    (l) => !isRemote(folder.source) && l.id === folder.source.location
  )
  return `${loc?.name ?? "?"}/${folder.path}`
}

/**
 * Choose a location or remote, then browse to a folder in it. `blocked` greys out
 * folders that can't be picked (a folder can't be copied into itself).
 */
export function FolderPicker({
  id,
  label,
  value,
  onChange,
  locations,
  remotes,
  blocked,
  onStatus,
}: {
  id: string
  label: string
  value: Folder
  onChange: (folder: Folder) => void
  locations: Location[]
  remotes: Remote[]
  blocked?: (folder: Folder) => boolean
  /** Whether the current folder could be listed (false on an error). */
  onStatus?: (ok: boolean | null) => void
}) {
  const [folders, setFolders] = React.useState<string[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const key = sourceKey(value.source)
  const onStatusRef = React.useRef(onStatus)
  onStatusRef.current = onStatus

  React.useEffect(() => {
    let live = true
    setFolders(null)
    setError(null)
    onStatusRef.current?.(null)
    void listFolders({ source: sourceFromKey(key), path: value.path }).then(
      (result) => {
        if (!live) return
        if ("error" in result) {
          setError(result.error)
          setFolders([])
        } else setFolders(result.names)
        onStatusRef.current?.(!("error" in result))
      }
    )
    return () => {
      live = false
    }
  }, [key, value.path])

  const localItems = locations.map((l) => ({
    value: sourceKey({ location: l.id }),
    label: l.name,
  }))
  const remoteItems = remotes.map((r) => ({
    value: sourceKey({ remote: r.name }),
    label: r.name,
  }))

  return (
    <div className="flex flex-col gap-3">
      <Field>
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        <Select
          items={[...localItems, ...remoteItems]}
          value={key}
          onValueChange={(v) => v && onChange({ source: sourceFromKey(v), path: "" })}
        >
          <SelectTrigger id={id} className="w-full">
            {isRemote(value.source) ? <CloudIcon /> : <HardDriveIcon />}
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {remoteItems.length ? <SelectLabel>Locations</SelectLabel> : null}
              {localItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
            {remoteItems.length ? (
              <SelectGroup>
                <SelectLabel>Cloud</SelectLabel>
                {remoteItems.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            ) : null}
          </SelectContent>
        </Select>
      </Field>
      <div className="rounded-lg border">
        <div className="flex items-center gap-2 border-b px-2 py-1.5">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Up one folder"
            disabled={!value.path}
            onClick={() => onChange({ ...value, path: parentOf(value.path) })}
          >
            <ArrowUpIcon />
          </Button>
          <span className="truncate font-mono text-xs text-muted-foreground">
            {folderLabel(value, locations, remotes)}
          </span>
        </div>
        <div className="h-44 overflow-y-auto p-1">
          {folders === null ? (
            <Skeleton className="h-8 w-full" />
          ) : error ? (
            <p className="p-2 text-sm text-destructive">{error}</p>
          ) : folders.length === 0 ? (
            <p className="p-2 text-sm text-muted-foreground">No folders here.</p>
          ) : (
            folders.map((name) => {
              const next = { ...value, path: joinPath(value.path, name) }
              return (
                <Button
                  key={name}
                  variant="ghost"
                  className="w-full justify-start"
                  disabled={blocked?.(next)}
                  onClick={() => onChange(next)}
                >
                  <FolderIcon />
                  <span className="truncate">{name}</span>
                </Button>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
