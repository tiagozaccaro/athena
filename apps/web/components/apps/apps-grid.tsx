"use client"

import * as React from "react"
import Link from "next/link"
import {
  EllipsisVerticalIcon,
  LayoutGridIcon,
  PlayIcon,
  PlusIcon,
  RefreshCcwIcon,
  RotateCwIcon,
  SquareIcon,
  Trash2Icon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
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

import {
  AppStatusBadge,
  DeleteAppDialog,
  OpenLinks,
} from "@/components/apps/app-bits"
import { useAppJobs } from "@/components/apps/use-app-jobs"

type AppOut = Schemas["AppOut"]

const REFRESH_MS = 10_000

export function AppsGrid() {
  const [apps, setApps] = React.useState<AppOut[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [removing, setRemoving] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    const { data, error: err } = await api.GET("/api/apps")
    if (data) {
      setApps(data)
      setError(null)
    } else setError(errorMessage(err, "Couldn't list apps"))
  }, [])

  React.useEffect(() => {
    void load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [load])

  const jobs = useAppJobs(() => void load())

  if (error && !apps) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>Couldn&apos;t list apps</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  if (!apps) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-36 w-full" />
        ))}
      </div>
    )
  }

  if (apps.length === 0) {
    return (
      <>
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <LayoutGridIcon />
            </EmptyMedia>
            <EmptyTitle>No apps yet</EmptyTitle>
            <EmptyDescription>
              Deploy a compose file or convert a <code>docker run</code>{" "}
              command.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button render={<Link href="/apps/new/" />}>
              <PlusIcon data-icon="inline-start" />
              New app
            </Button>
          </EmptyContent>
        </Empty>
        {jobs.dialog}
      </>
    )
  }

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {apps.map((app) => (
          <Card key={app.name}>
            <CardHeader>
              <CardTitle>
                <Link
                  href={`/apps/view/?name=${encodeURIComponent(app.name)}`}
                  className="hover:underline"
                >
                  {app.name}
                </Link>
              </CardTitle>
              <CardDescription>
                {app.total === 1 ? "1 container" : `${app.total} containers`}
                {app.source === "docker-run" ? " · from docker run" : ""}
              </CardDescription>
              <CardAction>
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={<Button variant="ghost" size="icon" />}
                  >
                    <EllipsisVerticalIcon />
                    <span className="sr-only">Actions for {app.name}</span>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="min-w-44">
                    <DropdownMenuGroup>
                      {app.status === "running" ? (
                        <>
                          <DropdownMenuItem
                            onClick={() => jobs.action(app.name, "restart")}
                          >
                            <RotateCwIcon />
                            Restart
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => jobs.action(app.name, "stop")}
                          >
                            <SquareIcon />
                            Stop
                          </DropdownMenuItem>
                        </>
                      ) : (
                        <DropdownMenuItem
                          onClick={() => jobs.action(app.name, "start")}
                        >
                          <PlayIcon />
                          Start
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        onClick={() => jobs.action(app.name, "update")}
                      >
                        <RefreshCcwIcon />
                        Update images
                      </DropdownMenuItem>
                    </DropdownMenuGroup>
                    <DropdownMenuSeparator />
                    <DropdownMenuGroup>
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => setRemoving(app.name)}
                      >
                        <Trash2Icon />
                        Remove
                      </DropdownMenuItem>
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </CardAction>
            </CardHeader>
            <CardFooter className="mt-auto flex flex-wrap items-center gap-2">
              <AppStatusBadge app={app} />
              <div className="ml-auto flex flex-wrap gap-2">
                <OpenLinks app={app} />
              </div>
            </CardFooter>
          </Card>
        ))}
      </div>
      <DeleteAppDialog
        name={removing}
        onCancel={() => setRemoving(null)}
        onConfirm={(deleteData) => {
          const name = removing
          setRemoving(null)
          if (name) void jobs.remove(name, deleteData)
        }}
      />
      {jobs.dialog}
    </>
  )
}
