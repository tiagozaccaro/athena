"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import {
  CloudIcon,
  CopyIcon,
  DownloadIcon,
  EllipsisVerticalIcon,
  EyeIcon,
  FolderInputIcon,
  FolderOpenIcon,
  FolderPlusIcon,
  HardDriveIcon,
  PencilIcon,
  RefreshCwIcon,
  Settings2Icon,
  Share2Icon,
  Trash2Icon,
  UploadIcon,
  XIcon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Badge } from "@workspace/ui/components/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@workspace/ui/components/breadcrumb"
import { Button } from "@workspace/ui/components/button"
import { Checkbox } from "@workspace/ui/components/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Field, FieldError, FieldLabel } from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Label } from "@workspace/ui/components/label"
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
import { Spinner } from "@workspace/ui/components/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { toast } from "@workspace/ui/components/toast"
import { Toggle } from "@workspace/ui/components/toggle"
import { cn } from "@workspace/ui/lib/utils"

import { useAuth } from "@/components/auth-provider"
import { useRemotes } from "@/components/cloud/use-remotes"
import { FilePreview } from "@/components/files/file-preview"
import {
  downloadUrl,
  type FileEntry,
  folderHref,
  formatModified,
  iconOf,
  isRemote,
  type Location,
  sameSource,
  type Source,
  sourceFromKey,
  sourceKey,
} from "@/components/files/file-utils"
import { LocationsDialog } from "@/components/files/locations-dialog"
import { ShareDialog, type ShareTarget } from "@/components/files/share-dialog"
import {
  TransferDialog,
  type TransferRequest,
  type TransferStart,
} from "@/components/files/transfer-dialog"
import { UploadsPanel } from "@/components/files/uploads-panel"
import { useUploads } from "@/components/files/use-uploads"
import { JobDialog } from "@/components/job-dialog"
import { formatBytes } from "@/lib/format"

type Job = Schemas["JobOut"]
type Listing = Schemas["Listing"]
type ListState =
  | { status: "loading" }
  | { status: "ok"; data: Listing }
  | { status: "error"; error: string; code: number }

const HIDDEN_KEY = "athena.files.hidden"

function readShowHidden(): boolean {
  try {
    return localStorage.getItem(HIDDEN_KEY) === "1"
  } catch {
    return false
  }
}

/** A name prompt for New folder and Rename. */
function NameDialog({
  title,
  action,
  initial,
  onClose,
  onSubmit,
}: {
  title: string | null
  action: string
  initial: string
  onClose: () => void
  onSubmit: (name: string) => Promise<string | null>
}) {
  const [name, setName] = React.useState(initial)
  const [error, setError] = React.useState<string | null>(null)
  const [pending, setPending] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    setName(initial)
    setError(null)
  }, [initial, title])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    const failed = await onSubmit(name.trim())
    setPending(false)
    setError(failed)
  }

  return (
    <Dialog open={title !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md" initialFocus={inputRef}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor="entry-name">Name</FieldLabel>
            <Input
              ref={inputRef}
              id="entry-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onFocus={(e) => {
                // Select the name without its extension, like a desktop file manager.
                const dot = e.target.value.lastIndexOf(".")
                e.target.setSelectionRange(
                  0,
                  dot > 0 ? dot : e.target.value.length
                )
              }}
              aria-invalid={error ? true : undefined}
              required
            />
            {error ? <FieldError>{error}</FieldError> : null}
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending || !name.trim()}>
              {pending ? <Spinner data-icon="inline-start" /> : null}
              {action}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function DeleteDialog({
  names,
  remote,
  onClose,
  onConfirm,
}: {
  names: string[] | null
  /** On a remote there's no trash: deletes are permanent. */
  remote: boolean
  onClose: () => void
  onConfirm: (permanent: boolean) => void
}) {
  const [permanent, setPermanent] = React.useState(false)
  React.useEffect(() => setPermanent(false), [names])
  const what = names?.length === 1 ? names[0] : `${names?.length ?? 0} items`
  return (
    <AlertDialog open={names !== null} onOpenChange={(o) => !o && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {what}?</AlertDialogTitle>
          <AlertDialogDescription>
            {remote
              ? "It's deleted from the remote. Some services keep their own trash; Athena can't restore it."
              : permanent
                ? "This can't be undone."
                : "It goes to the server's trash, where you can restore it from the desktop."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {remote ? null : (
          <div className="flex items-center gap-2">
            <Checkbox
              id="delete-permanent"
              checked={permanent}
              onCheckedChange={(c) => setPermanent(c === true)}
            />
            <Label htmlFor="delete-permanent">Delete permanently</Label>
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => onConfirm(permanent)}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

/** The file manager: one location or cloud remote at a time, a folder per URL
 * (?loc=&path= or ?remote=&path=). */
export function FilesView() {
  const router = useRouter()
  const params = useSearchParams()
  const { user } = useAuth()
  const { remotes } = useRemotes()
  const [locations, setLocations] = React.useState<Location[] | null>(null)
  const [locationsOpen, setLocationsOpen] = React.useState(false)
  const [list, setList] = React.useState<ListState>({ status: "loading" })
  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [showHidden, setShowHidden] = React.useState(false)
  const [preview, setPreview] = React.useState<FileEntry | null>(null)
  const [naming, setNaming] = React.useState<
    { kind: "folder" } | { kind: "rename"; entry: FileEntry } | null
  >(null)
  const [deleting, setDeleting] = React.useState<string[] | null>(null)
  const [transfer, setTransfer] = React.useState<TransferRequest | null>(null)
  const [job, setJob] = React.useState<Job | null>(null)
  const [sharing, setSharing] = React.useState<ShareTarget | null>(null)
  const [dragging, setDragging] = React.useState(false)
  const fileInput = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => setShowHidden(readShowHidden()), [])

  const loadLocations = React.useCallback(async () => {
    const { data } = await api.GET("/api/files/locations")
    setLocations(data ?? [])
  }, [])
  React.useEffect(() => {
    void loadLocations()
  }, [loadLocations])

  const remoteName = params.get("remote")
  const requested = Number(params.get("loc")) || null
  const path = params.get("path") ?? ""
  const remote = remoteName
    ? remotes?.find((r) => r.name === remoteName)
    : undefined
  const location = remoteName
    ? undefined
    : (locations?.find((l) => l.id === requested) ??
      (requested === null
        ? (locations?.find((l) => l.available) ?? locations?.[0])
        : undefined))
  const locId = location?.id ?? 0
  const source: Source = remoteName ? { remote: remoteName } : { location: locId }
  const key = sourceKey(source)
  // What the toolbar shows for the current location or remote.
  const place = remote
    ? { name: remote.name, available: true, writable: true }
    : location

  const load = React.useCallback(async () => {
    const current = sourceFromKey(key)
    if (!isRemote(current) && !current.location) return
    const { data, error, response } = isRemote(current)
      ? await api.GET("/api/cloud/files/list", {
          params: { query: { remote: current.remote, path } },
        })
      : await api.GET("/api/files/list", {
          params: { query: { location: current.location, path } },
        })
    if (data) setList({ status: "ok", data })
    else
      setList({
        status: "error",
        error: errorMessage(error),
        code: response.status,
      })
  }, [key, path])

  React.useEffect(() => {
    setList({ status: "loading" })
    setSelected(new Set())
    void load()
  }, [load])

  const uploads = useUploads((src, folder) => {
    if (sameSource(src, source) && folder === path) void load()
  })

  const go = (target: string, to: Source = source) =>
    router.push(folderHref(to, target))

  const entries =
    list.status === "ok"
      ? list.data.entries.filter((e) => showHidden || !e.hidden)
      : []
  const chosen = entries.filter((e) => selected.has(e.path))
  const allChosen = entries.length > 0 && chosen.length === entries.length

  function toggle(entryPath: string, on: boolean) {
    setSelected((s) => {
      const next = new Set(s)
      if (on) next.add(entryPath)
      else next.delete(entryPath)
      return next
    })
  }

  function open(entry: FileEntry) {
    if (entry.kind === "dir") go(entry.path)
    else setPreview(entry)
  }

  function startUpload(files: FileList | File[] | null) {
    if (!files || !place) return
    const all = Array.from(files)
    if (all.length) uploads.add(all, source, path)
  }

  async function submitName(name: string): Promise<string | null> {
    if (!naming) return null
    const result = isRemote(source)
      ? naming.kind === "folder"
        ? await api.POST("/api/cloud/files/folder", {
            body: { remote: source.remote, path, name },
          })
        : await api.POST("/api/cloud/files/rename", {
            body: { remote: source.remote, path: naming.entry.path, name },
          })
      : naming.kind === "folder"
        ? await api.POST("/api/files/folder", {
            body: { location: locId, path, name },
          })
        : await api.POST("/api/files/rename", {
            body: { location: locId, path: naming.entry.path, name },
          })
    if (!result.data) return errorMessage(result.error)
    setNaming(null)
    void load()
    return null
  }

  async function remove(paths: string[], permanent: boolean) {
    setDeleting(null)
    const { data, error } = isRemote(source)
      ? await api.POST("/api/cloud/files/delete", {
          body: { remote: source.remote, paths },
        })
      : await api.POST("/api/files/delete", {
          body: { location: locId, paths, permanent },
        })
    void load()
    if (!data) {
      toast.add({
        type: "error",
        title: "Couldn't delete",
        description: errorMessage(error),
      })
      return
    }
    if (data.deleted.length) {
      toast.add({
        type: "success",
        title:
          data.deleted.length === 1
            ? `Deleted ${data.deleted[0]!.split("/").pop()}`
            : `Deleted ${data.deleted.length} items`,
      })
    }
    for (const failed of data.errors) {
      toast.add({
        type: "error",
        title: `Couldn't delete ${failed.path.split("/").pop()}`,
        description: failed.error,
      })
    }
  }

  async function startTransfer(start: TransferStart) {
    setTransfer(null)
    const { data, error } =
      start.kind === "files"
        ? await api.POST("/api/files/transfer", { body: start.body })
        : await api.POST("/api/cloud/transfer", { body: start.body })
    if (data) setJob(data)
    else
      toast.add({
        type: "error",
        title: `Couldn't ${start.body.op}`,
        description: errorMessage(error),
      })
  }

  if (locations === null || (remoteName && remotes === null)) {
    return <Skeleton className="h-96 w-full" />
  }

  if (remoteName && !remote) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <CloudIcon />
          </EmptyMedia>
          <EmptyTitle>No such remote</EmptyTitle>
          <EmptyDescription>
            There&apos;s no cloud remote called {remoteName}, or rclone isn&apos;t
            available on this host.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button render={<Link href="/cloud/" />} nativeButton={false}>
            Go to Cloud
          </Button>
        </EmptyContent>
      </Empty>
    )
  }

  if (!place) {
    return (
      <>
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <HardDriveIcon />
            </EmptyMedia>
            <EmptyTitle>
              {locations.length ? "No such location" : "No locations"}
            </EmptyTitle>
            <EmptyDescription>
              The file manager only shows folders added as locations.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            {locations.length ? (
              <Button render={<Link href="/files/" />} nativeButton={false}>
                Go to {locations[0]!.name}
              </Button>
            ) : user.is_admin ? (
              <Button onClick={() => setLocationsOpen(true)}>
                Add a location
              </Button>
            ) : null}
          </EmptyContent>
        </Empty>
        <LocationsDialog
          open={locationsOpen}
          locations={locations}
          onOpenChange={setLocationsOpen}
          onChanged={loadLocations}
        />
      </>
    )
  }

  const crumbs = path ? path.split("/") : []
  const localItems = locations.map((l) => ({
    value: sourceKey({ location: l.id }),
    label: l.name,
  }))
  const remoteItems = (remotes ?? []).map((r) => ({
    value: sourceKey({ remote: r.name }),
    label: r.name,
  }))
  const onRemote = isRemote(source)
  const readOnly = !place.writable

  const rowMenu = (entry: FileEntry) => (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="ghost" size="icon" />}>
        <EllipsisVerticalIcon />
        <span className="sr-only">Actions for {entry.name}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40">
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={() => open(entry)}>
            {entry.kind === "dir" ? <FolderOpenIcon /> : <EyeIcon />}
            Open
          </DropdownMenuItem>
          {onRemote && entry.kind === "dir" ? null : (
            <DropdownMenuItem
              render={<a href={downloadUrl(source, entry.path)} download />}
            >
              <DownloadIcon />
              {entry.kind === "dir" ? "Download as zip" : "Download"}
            </DropdownMenuItem>
          )}
          {onRemote ? null : (
            <DropdownMenuItem
              disabled={entry.kind === "other"}
              onClick={() =>
                setSharing({
                  location: locId,
                  path: entry.path,
                  name: entry.name,
                  kind: entry.kind,
                })
              }
            >
              <Share2Icon />
              Share…
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem
            disabled={readOnly}
            onClick={() => setNaming({ kind: "rename", entry })}
          >
            <PencilIcon />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() =>
              setTransfer({ op: "copy", source, paths: [entry.path] })
            }
          >
            <CopyIcon />
            Copy to…
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={readOnly}
            onClick={() =>
              setTransfer({ op: "move", source, paths: [entry.path] })
            }
          >
            <FolderInputIcon />
            Move to…
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem
            variant="destructive"
            disabled={readOnly}
            onClick={() => setDeleting([entry.path])}
          >
            <Trash2Icon />
            Delete
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          items={[...localItems, ...remoteItems]}
          value={key}
          onValueChange={(v) => v && go("", sourceFromKey(v))}
        >
          <SelectTrigger className="w-full sm:w-56" aria-label="Location">
            {onRemote ? <CloudIcon /> : <HardDriveIcon />}
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
        {user.is_admin ? (
          <Button
            variant="outline"
            size="icon"
            aria-label="Manage locations"
            onClick={() => setLocationsOpen(true)}
          >
            <Settings2Icon />
          </Button>
        ) : null}
        {onRemote ? (
          <Badge variant="outline">{remote?.description}</Badge>
        ) : !place.available ? (
          <Badge variant="destructive">Missing</Badge>
        ) : readOnly ? (
          <Badge variant="secondary">Read-only</Badge>
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Toggle
            variant="outline"
            pressed={showHidden}
            onPressedChange={(on) => {
              setShowHidden(on)
              try {
                localStorage.setItem(HIDDEN_KEY, on ? "1" : "0")
              } catch {}
            }}
            aria-label="Show hidden files"
          >
            <EyeIcon />
            <span className="hidden sm:inline">Hidden</span>
          </Toggle>
          <Button
            variant="outline"
            render={<Link href="/files/shares/" />}
            nativeButton={false}
            aria-label="Share links"
          >
            <Share2Icon />
            <span className="hidden sm:inline">Links</span>
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="Refresh"
            onClick={() => void load()}
          >
            <RefreshCwIcon />
          </Button>
          <Button
            variant="outline"
            disabled={readOnly || list.status !== "ok"}
            onClick={() => setNaming({ kind: "folder" })}
            aria-label="New folder"
          >
            <FolderPlusIcon />
            <span className="hidden sm:inline">New folder</span>
          </Button>
          <Button
            disabled={readOnly || list.status !== "ok"}
            onClick={() => fileInput.current?.click()}
          >
            <UploadIcon />
            Upload
          </Button>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              startUpload(e.target.files)
              e.target.value = ""
            }}
          />
        </div>
      </div>

      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            {crumbs.length ? (
              <BreadcrumbLink render={<Link href={folderHref(source, "")} />}>
                {place.name}
              </BreadcrumbLink>
            ) : (
              <BreadcrumbPage>{place.name}</BreadcrumbPage>
            )}
          </BreadcrumbItem>
          {crumbs.map((name, i) => {
            const target = crumbs.slice(0, i + 1).join("/")
            const last = i === crumbs.length - 1
            return (
              <React.Fragment key={target}>
                <BreadcrumbSeparator />
                <BreadcrumbItem className="min-w-0">
                  {last ? (
                    <BreadcrumbPage className="truncate">{name}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink
                      className="truncate"
                      render={<Link href={folderHref(source, target)} />}
                    >
                      {name}
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
              </React.Fragment>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>

      {chosen.length ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2">
          <span className="text-sm font-medium">{chosen.length} selected</span>
          <div className="ml-auto flex flex-wrap gap-2">
            {chosen.length === 1 && !(onRemote && chosen[0]!.kind === "dir") ? (
              <Button
                variant="outline"
                size="sm"
                nativeButton={false}
                render={
                  <a href={downloadUrl(source, chosen[0]!.path)} download />
                }
              >
                <DownloadIcon />
                Download
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setTransfer({
                  op: "copy",
                  source,
                  paths: chosen.map((e) => e.path),
                })
              }
            >
              <CopyIcon />
              Copy
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={readOnly}
              onClick={() =>
                setTransfer({
                  op: "move",
                  source,
                  paths: chosen.map((e) => e.path),
                })
              }
            >
              <FolderInputIcon />
              Move
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={readOnly}
              onClick={() => setDeleting(chosen.map((e) => e.path))}
            >
              <Trash2Icon />
              Delete
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Clear selection"
              onClick={() => setSelected(new Set())}
            >
              <XIcon />
            </Button>
          </div>
        </div>
      ) : null}

      <div
        className={cn(
          "relative rounded-lg border",
          dragging && "border-primary ring-3 ring-primary/30"
        )}
        onDragOver={(e) => {
          if (readOnly || !e.dataTransfer.types.includes("Files")) return
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node))
            setDragging(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!readOnly) startUpload(e.dataTransfer.files)
        }}
      >
        {dragging ? (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/80 text-sm font-medium">
            Drop to upload to {path.split("/").pop() || place.name}
          </div>
        ) : null}
        {list.status === "loading" ? (
          <div className="flex flex-col gap-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-2/3" />
          </div>
        ) : list.status === "error" ? (
          <div className="p-4">
            <Alert variant="destructive">
              <AlertTitle>
                {list.code === 404 ? "Not found" : "Can't open this folder"}
              </AlertTitle>
              <AlertDescription>
                {list.error}
                {path ? (
                  <Button
                    variant="link"
                    className="h-auto p-0"
                    render={<Link href={folderHref(source, "")} />}
                    nativeButton={false}
                  >
                    Back to {place.name}
                  </Button>
                ) : null}
              </AlertDescription>
            </Alert>
          </div>
        ) : entries.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FolderOpenIcon />
              </EmptyMedia>
              <EmptyTitle>This folder is empty</EmptyTitle>
              <EmptyDescription>
                {readOnly
                  ? "Athena can't write to this location."
                  : "Upload files or drop them here."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="Select all"
                    checked={allChosen}
                    indeterminate={chosen.length > 0 && !allChosen}
                    onCheckedChange={(on) =>
                      setSelected(
                        on ? new Set(entries.map((e) => e.path)) : new Set()
                      )
                    }
                  />
                </TableHead>
                <TableHead>Name</TableHead>
                <TableHead className="hidden w-28 text-right sm:table-cell">
                  Size
                </TableHead>
                <TableHead className="hidden w-44 md:table-cell">
                  Modified
                </TableHead>
                <TableHead className="w-12">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => {
                const Icon = iconOf(entry)
                return (
                  <TableRow
                    key={entry.path}
                    data-state={
                      selected.has(entry.path) ? "selected" : undefined
                    }
                  >
                    <TableCell>
                      <Checkbox
                        aria-label={`Select ${entry.name}`}
                        checked={selected.has(entry.path)}
                        onCheckedChange={(on) =>
                          toggle(entry.path, on === true)
                        }
                      />
                    </TableCell>
                    <TableCell className="max-w-0">
                      <button
                        type="button"
                        className={cn(
                          "flex w-full min-w-0 items-center gap-2 text-left hover:underline",
                          entry.hidden && "text-muted-foreground"
                        )}
                        onClick={() => open(entry)}
                      >
                        <Icon
                          className={cn(
                            "size-4 shrink-0",
                            entry.kind === "dir"
                              ? "text-primary"
                              : "text-muted-foreground"
                          )}
                        />
                        <span className="truncate">{entry.name}</span>
                        {entry.is_link ? (
                          <Badge variant="outline" className="shrink-0">
                            link
                          </Badge>
                        ) : null}
                      </button>
                    </TableCell>
                    <TableCell className="hidden text-right text-muted-foreground tabular-nums sm:table-cell">
                      {entry.size != null ? formatBytes(entry.size) : "—"}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground md:table-cell">
                      {formatModified(entry.modified)}
                    </TableCell>
                    <TableCell>{rowMenu(entry)}</TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
        {list.status === "ok" && list.data.truncated ? (
          <p className="border-t p-3 text-sm text-muted-foreground">
            Only the first {list.data.entries.length.toLocaleString()} entries
            are shown.
          </p>
        ) : null}
      </div>

      <NameDialog
        title={
          naming?.kind === "folder"
            ? "New folder"
            : naming?.kind === "rename"
              ? `Rename ${naming.entry.name}`
              : null
        }
        action={naming?.kind === "folder" ? "Create" : "Rename"}
        initial={naming?.kind === "rename" ? naming.entry.name : ""}
        onClose={() => setNaming(null)}
        onSubmit={submitName}
      />
      <DeleteDialog
        names={deleting?.map((p) => p.split("/").pop() ?? p) ?? null}
        remote={onRemote}
        onClose={() => setDeleting(null)}
        onConfirm={(permanent) => deleting && void remove(deleting, permanent)}
      />
      <TransferDialog
        request={transfer}
        locations={locations.filter((l) => l.available)}
        remotes={remotes ?? []}
        onClose={() => setTransfer(null)}
        onStart={startTransfer}
      />
      <JobDialog
        job={job}
        onClose={() => setJob(null)}
        onFinished={() => {
          setSelected(new Set())
          void load()
        }}
      />
      <FilePreview
        source={source}
        // The listing's copy, so the size follows a save.
        entry={
          (preview && entries.find((e) => e.path === preview.path)) ?? preview
        }
        onClose={() => setPreview(null)}
        onSaved={() => void load()}
      />
      <LocationsDialog
        open={locationsOpen}
        locations={locations}
        onOpenChange={setLocationsOpen}
        onChanged={loadLocations}
      />
      <ShareDialog target={sharing} onClose={() => setSharing(null)} />
      <UploadsPanel
        uploads={uploads.uploads}
        onCancel={uploads.cancel}
        onRetry={uploads.retry}
        onClear={uploads.clear}
      />
    </div>
  )
}
