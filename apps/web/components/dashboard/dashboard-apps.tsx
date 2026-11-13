"use client"

import Link from "next/link"
import { LayoutGridIcon, PlayIcon, SquareIcon, StoreIcon } from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from "@workspace/ui/components/item"
import { Skeleton } from "@workspace/ui/components/skeleton"

import { AppStatusBadge, OpenLinks } from "@/components/apps/app-bits"
import { useAppJobs } from "@/components/apps/use-app-jobs"
import { type AppOut, useAppsList } from "@/components/apps/use-apps-list"
import { isAllowed, useCapabilities } from "@/components/capabilities-provider"
import { RuntimeEmpty } from "@/components/containers/runtime-empty"
import { AppIcon } from "@/components/store/app-icon"

function AppTile({
  app,
  onAction,
}: {
  app: AppOut
  onAction: (name: string, action: "start" | "stop") => void
}) {
  const up = app.status === "running" || app.status === "partial"
  const href = `/apps/view/?name=${encodeURIComponent(app.name)}`
  return (
    <Item variant="outline" size="sm" className="flex-nowrap">
      <ItemMedia>
        <AppIcon
          title={app.title ?? app.name}
          icon={app.icon}
          className="size-9"
        />
      </ItemMedia>
      <ItemContent className="min-w-0">
        <ItemTitle className="w-full min-w-0">
          <Link href={href} className="truncate hover:underline">
            {app.name}
          </Link>
        </ItemTitle>
        <ItemDescription className="flex items-center gap-2">
          <AppStatusBadge app={app} />
          {app.title && app.title.toLowerCase() !== app.name.toLowerCase() ? (
            <span className="truncate">{app.title}</span>
          ) : null}
        </ItemDescription>
      </ItemContent>
      <ItemActions>
        <OpenLinks app={app} />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={`${up ? "Stop" : "Start"} ${app.name}`}
          title={up ? "Stop" : "Start"}
          onClick={() => onAction(app.name, up ? "stop" : "start")}
        >
          {up ? <SquareIcon /> : <PlayIcon />}
        </Button>
      </ItemActions>
    </Item>
  )
}

function AppsList() {
  const { apps, error, load } = useAppsList()
  const jobs = useAppJobs(() => void load())

  if (error && !apps) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (!apps) {
    return (
      <div className="grid gap-3 @3xl/main:grid-cols-2 @6xl/main:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }
  if (apps.length === 0) {
    return (
      <Empty className="border py-8">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <LayoutGridIcon />
          </EmptyMedia>
          <EmptyTitle>No apps yet</EmptyTitle>
          <EmptyDescription>
            Install one from the store, or deploy your own compose file.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button render={<Link href="/store/" />}>
            <StoreIcon data-icon="inline-start" />
            Browse the store
          </Button>
        </EmptyContent>
      </Empty>
    )
  }
  return (
    <>
      <div className="grid gap-3 @3xl/main:grid-cols-2 @6xl/main:grid-cols-3">
        {apps.map((app) => (
          <AppTile
            key={app.name}
            app={app}
            // Reload right away too, so a failed action (e.g. the app was removed
            // elsewhere) doesn't leave a stale tile until the next refresh.
            onAction={(name, act) => void jobs.action(name, act).then(load)}
          />
        ))}
      </div>
      {jobs.dialog}
    </>
  )
}

/** The dashboard's app grid: status, Open links and start/stop, or the runtime's Start/setup. */
export function DashboardApps() {
  const { manifest } = useCapabilities()
  const containers = manifest?.capabilities.find((c) => c.id === "containers")
  // Same rule as the Apps nav item: hidden only where containers can't work at all.
  if (manifest && !isAllowed(manifest, "containers", true)) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Apps</CardTitle>
        <CardDescription>What&apos;s running on this server</CardDescription>
        <CardAction className="flex gap-2">
          <Button variant="outline" size="sm" render={<Link href="/store/" />}>
            <StoreIcon data-icon="inline-start" />
            Store
          </Button>
          <Button variant="ghost" size="sm" render={<Link href="/apps/" />}>
            All apps
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {!manifest ? (
          <Skeleton className="h-16 w-full" />
        ) : containers?.available ? (
          <AppsList />
        ) : (
          <RuntimeEmpty capability={containers} />
        )}
      </CardContent>
    </Card>
  )
}
