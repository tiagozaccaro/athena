"use client"

import * as React from "react"
import Link from "next/link"
import {
  CloudIcon,
  EllipsisVerticalIcon,
  FolderOpenIcon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
  RefreshCcwDotIcon,
  Trash2Icon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
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
import { Button } from "@workspace/ui/components/button"
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

import { useAuth } from "@/components/auth-provider"
import {
  useCapabilities,
  useCapability,
} from "@/components/capabilities-provider"
import { RemoteDialog, type RemoteEditing } from "@/components/cloud/remote-dialog"
import { SyncDialog } from "@/components/cloud/sync-dialog"
import { useRemotes } from "@/components/cloud/use-remotes"
import { folderHref, type Location } from "@/components/files/file-utils"
import { JobDialog } from "@/components/job-dialog"

type Job = Schemas["JobOut"]

/** How to install rclone on each OS. */
const SETUP: Record<string, string[]> = {
  darwin: ["brew install rclone"],
  linux: [
    "sudo apt install rclone      # Debian, Ubuntu",
    "sudo dnf install rclone      # Fedora",
    "sudo pacman -S rclone        # Arch",
    "or the latest release: curl https://rclone.org/install.sh | sudo bash",
  ],
  windows: ["winget install Rclone.Rclone", "or: choco install rclone"],
}

/** End with a full stop: details come from the server without one. */
function sentence(text: string): string {
  return /[.!?]$/.test(text) ? text : `${text}.`
}

function NoRclone({ detail }: { detail?: string | null }) {
  const { manifest, refresh, refreshing } = useCapabilities()
  const steps = SETUP[manifest?.os ?? "linux"] ?? SETUP.linux!
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CloudIcon />
        </EmptyMedia>
        <EmptyTitle>Cloud storage needs rclone</EmptyTitle>
        <EmptyDescription>
          {sentence(detail ?? "rclone isn't installed on this host")} Athena uses rclone
          to connect to Google Drive, OneDrive, Dropbox, S3 and many more.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <div className="flex w-full flex-col gap-2 text-left">
          <p className="text-sm font-medium">Install rclone on the server</p>
          <pre className="rounded-lg border bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap">
            {steps.join("\n")}
          </pre>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={refreshing}
        >
          {refreshing ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <RefreshCwIcon data-icon="inline-start" />
          )}
          Re-detect
        </Button>
      </EmptyContent>
    </Empty>
  )
}

/** Cloud remotes (rclone): add, edit, remove, browse in Files, and sync folders. */
export function CloudView() {
  const { user } = useAuth()
  const capability = useCapability("cloud.rclone")
  const { remotes, error, reload } = useRemotes()
  const [editing, setEditing] = React.useState<RemoteEditing>(null)
  const [removing, setRemoving] = React.useState<string | null>(null)
  const [syncing, setSyncing] = React.useState(false)
  const [job, setJob] = React.useState<Job | null>(null)
  const [locations, setLocations] = React.useState<Location[]>([])

  React.useEffect(() => {
    void api
      .GET("/api/files/locations")
      .then(({ data }) => setLocations((data ?? []).filter((l) => l.available)))
  }, [])

  if (capability === undefined) return <Skeleton className="h-64 w-full" />
  if (capability.status !== "ready") return <NoRclone detail={capability.detail} />

  async function remove(name: string) {
    setRemoving(null)
    const { error } = await api.DELETE("/api/cloud/remotes/{name}", {
      params: { path: { name } },
    })
    void reload()
    if (error)
      toast.add({
        type: "error",
        title: `Couldn't remove ${name}`,
        description: errorMessage(error),
      })
    else toast.add({ type: "success", title: `Removed ${name}` })
  }

  const admin = user.is_admin
  const list = remotes ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-muted-foreground">
          {capability.detail ?? "rclone"}
        </p>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="icon"
            aria-label="Refresh"
            onClick={() => void reload()}
          >
            <RefreshCwIcon />
          </Button>
          <Button
            variant="outline"
            disabled={!list.length && !locations.length}
            onClick={() => setSyncing(true)}
          >
            <RefreshCcwDotIcon />
            Sync folders
          </Button>
          {admin ? (
            <Button onClick={() => setEditing({ name: null })}>
              <PlusIcon />
              Add remote
            </Button>
          ) : null}
        </div>
      </div>

      {remotes === null ? (
        <Skeleton className="h-40 w-full" />
      ) : error ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Can&apos;t reach rclone</EmptyTitle>
            <EmptyDescription>{error}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : list.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <CloudIcon />
            </EmptyMedia>
            <EmptyTitle>No remotes yet</EmptyTitle>
            <EmptyDescription>
              Add Google Drive, OneDrive, Dropbox, an S3 bucket, a WebDAV server
              or any other storage rclone supports, then browse it in Files and
              copy or sync folders to it.
            </EmptyDescription>
          </EmptyHeader>
          {admin ? (
            <EmptyContent>
              <Button onClick={() => setEditing({ name: null })}>
                <PlusIcon />
                Add remote
              </Button>
            </EmptyContent>
          ) : null}
        </Empty>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="hidden sm:table-cell">Storage</TableHead>
                <TableHead className="w-12">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {list.map((remote) => (
                <TableRow key={remote.name}>
                  <TableCell className="max-w-0">
                    <Link
                      href={folderHref({ remote: remote.name }, "")}
                      className="flex min-w-0 items-center gap-2 hover:underline"
                    >
                      <CloudIcon className="size-4 shrink-0 text-primary" />
                      <span className="truncate font-medium">{remote.name}</span>
                    </Link>
                    <span className="text-xs text-muted-foreground sm:hidden">
                      {remote.description}
                    </span>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground sm:table-cell">
                    {remote.description}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger
                        render={<Button variant="ghost" size="icon" />}
                      >
                        <EllipsisVerticalIcon />
                        <span className="sr-only">
                          Actions for {remote.name}
                        </span>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="min-w-40">
                        <DropdownMenuGroup>
                          <DropdownMenuItem
                            render={
                              <Link href={folderHref({ remote: remote.name }, "")} />
                            }
                          >
                            <FolderOpenIcon />
                            Browse
                          </DropdownMenuItem>
                          {admin ? (
                            <DropdownMenuItem
                              onClick={() => setEditing({ name: remote.name })}
                            >
                              <PencilIcon />
                              Edit
                            </DropdownMenuItem>
                          ) : null}
                        </DropdownMenuGroup>
                        {admin ? (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuGroup>
                              <DropdownMenuItem
                                variant="destructive"
                                onClick={() => setRemoving(remote.name)}
                              >
                                <Trash2Icon />
                                Remove
                              </DropdownMenuItem>
                            </DropdownMenuGroup>
                          </>
                        ) : null}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <RemoteDialog
        editing={editing}
        onClose={() => setEditing(null)}
        onSaved={() => void reload()}
      />
      <AlertDialog
        open={removing !== null}
        onOpenChange={(o) => !o && setRemoving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing}?</AlertDialogTitle>
            <AlertDialogDescription>
              Athena forgets how to connect to it. Nothing stored on it is
              deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => removing && void remove(removing)}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <SyncDialog
        open={syncing}
        locations={locations}
        remotes={list}
        onClose={() => setSyncing(false)}
        onStarted={setJob}
      />
      <JobDialog job={job} onClose={() => setJob(null)} />
    </div>
  )
}
