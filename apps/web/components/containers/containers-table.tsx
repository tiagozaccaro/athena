"use client"

import * as React from "react"
import {
  EllipsisVerticalIcon,
  PlayIcon,
  RotateCwIcon,
  ScrollTextIcon,
  SquareTerminalIcon,
  SquareIcon,
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
import { Badge } from "@workspace/ui/components/badge"
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
  EmptyDescription,
  EmptyHeader,
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

import { LogsSheet } from "@/components/containers/logs-sheet"
import { ShellSheet } from "@/components/terminal/shell-sheet"
import { useTerminalAccess } from "@/components/terminal/use-terminal-access"

type Container = Schemas["ContainerOut"]
type Action = "start" | "stop" | "restart"

const REFRESH_MS = 10_000

function StateBadge({ c }: { c: Container }) {
  if (c.state === "running") return <Badge variant="secondary">Running</Badge>
  if (c.state === "dead") return <Badge variant="destructive">Dead</Badge>
  if (c.state === "exited") {
    return (
      <Badge variant="outline">
        Exited{c.exit_code ? ` (${c.exit_code})` : ""}
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="capitalize">
      {c.state}
    </Badge>
  )
}

function groups(containers: Container[]): [string, Container[]][] {
  const byProject = new Map<string, Container[]>()
  for (const c of containers) {
    const key = c.project ?? ""
    byProject.set(key, [...(byProject.get(key) ?? []), c])
  }
  return [...byProject.entries()].sort(([a], [b]) =>
    a === "" ? 1 : b === "" ? -1 : a.localeCompare(b)
  )
}

export function ContainersTable() {
  const [containers, setContainers] = React.useState<Container[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [logsFor, setLogsFor] = React.useState<Container | null>(null)
  const [shellFor, setShellFor] = React.useState<Container | null>(null)
  const canShell = useTerminalAccess().state === "ready"
  const [removing, setRemoving] = React.useState<Container | null>(null)

  const load = React.useCallback(async () => {
    const { data, error: err } = await api.GET("/api/containers")
    if (data) {
      setContainers(data)
      setError(null)
    } else {
      setError(errorMessage(err, "Couldn't list containers"))
    }
  }, [])

  React.useEffect(() => {
    void load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [load])

  async function act(c: Container, action: Action) {
    setBusy(c.id)
    const path = `/api/containers/{ref}/${action}` as const
    const { error: err } = await api.POST(path, {
      params: { path: { ref: c.id } },
    })
    setBusy(null)
    if (err) {
      toast.add({
        type: "error",
        title: `Couldn't ${action} ${c.name}`,
        description: errorMessage(err),
      })
    }
    await load()
  }

  async function remove(c: Container) {
    setBusy(c.id)
    const { error: err } = await api.DELETE("/api/containers/{ref}", {
      params: { path: { ref: c.id }, query: { force: c.state === "running" } },
    })
    setBusy(null)
    setRemoving(null)
    if (err) {
      toast.add({
        type: "error",
        title: `Couldn't remove ${c.name}`,
        description: errorMessage(err),
      })
    } else {
      toast.add({ type: "success", title: `Removed ${c.name}` })
    }
    await load()
  }

  if (error && !containers) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>Couldn&apos;t list containers</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  if (!containers) {
    return (
      <div className="flex flex-col gap-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    )
  }

  if (containers.length === 0) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>No containers yet</EmptyTitle>
          <EmptyDescription>
            Containers on this runtime show up here, including ones started
            outside Athena.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <>
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="bg-muted">
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="hidden md:table-cell">Image</TableHead>
              <TableHead>State</TableHead>
              <TableHead className="hidden lg:table-cell">Ports</TableHead>
              <TableHead className="w-10">
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups(containers).map(([project, rows]) => (
              <React.Fragment key={project || "~standalone"}>
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={5}
                    className="bg-muted/40 text-xs font-medium text-muted-foreground"
                  >
                    {project || "Standalone containers"}
                  </TableCell>
                </TableRow>
                {rows.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">
                      <div className="flex flex-col">
                        <span>{c.name}</span>
                        <span className="text-xs text-muted-foreground md:hidden">
                          {c.image}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="hidden max-w-64 truncate text-muted-foreground md:table-cell">
                      {c.image}
                    </TableCell>
                    <TableCell>
                      <StateBadge c={c} />
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground lg:table-cell">
                      {c.ports.join(", ") || "—"}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={busy === c.id}
                            />
                          }
                        >
                          {busy === c.id ? (
                            <Spinner />
                          ) : (
                            <EllipsisVerticalIcon />
                          )}
                          <span className="sr-only">Actions for {c.name}</span>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="min-w-40">
                          <DropdownMenuGroup>
                            <DropdownMenuItem onClick={() => setLogsFor(c)}>
                              <ScrollTextIcon />
                              Logs
                            </DropdownMenuItem>
                            {canShell && c.state === "running" && (
                              <DropdownMenuItem onClick={() => setShellFor(c)}>
                                <SquareTerminalIcon />
                                Shell
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuGroup>
                          <DropdownMenuSeparator />
                          <DropdownMenuGroup>
                            {c.state === "running" ? (
                              <>
                                <DropdownMenuItem
                                  onClick={() => act(c, "restart")}
                                >
                                  <RotateCwIcon />
                                  Restart
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => act(c, "stop")}
                                >
                                  <SquareIcon />
                                  Stop
                                </DropdownMenuItem>
                              </>
                            ) : (
                              <DropdownMenuItem onClick={() => act(c, "start")}>
                                <PlayIcon />
                                Start
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuGroup>
                          <DropdownMenuSeparator />
                          <DropdownMenuGroup>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setRemoving(c)}
                            >
                              <Trash2Icon />
                              Remove
                            </DropdownMenuItem>
                          </DropdownMenuGroup>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      </div>

      <LogsSheet container={logsFor} onClose={() => setLogsFor(null)} />
      <ShellSheet container={shellFor} onClose={() => setShellFor(null)} />

      <AlertDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              {removing?.state === "running"
                ? "It will be stopped first. "
                : ""}
              The container is deleted. Named volumes and the image are kept.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => removing && remove(removing)}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
