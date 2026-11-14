"use client"

import * as React from "react"
import { PackageIcon } from "lucide-react"

import { api, type Schemas } from "@workspace/api-client"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"

import { ManagerPanel } from "@/components/packages/manager-panel"
import { useApi } from "@/hooks/use-api"

type Manager = Schemas["ManagerOut"]

/** A tab per package manager detected on this host (docs/mvp-design.md §3). */
export function PackagesView() {
  const managers = useApi(() => api.GET("/api/packages"))
  const [tab, setTab] = React.useState<string | null>(null)

  if (managers.status === "loading") return <Skeleton className="h-64 w-full" />
  if (managers.status === "error" || managers.data.length === 0) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <PackageIcon />
          </EmptyMedia>
          <EmptyTitle>No package managers found</EmptyTitle>
          <EmptyDescription>
            {managers.status === "error"
              ? managers.error
              : "Athena didn't find a package manager it supports on this host."}
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  const list: Manager[] = managers.data
  const current =
    tab ?? (list.find((m) => m.available) ?? list[0])?.id ?? list[0]!.id
  return (
    <Tabs value={current} onValueChange={(v) => setTab(v as string)}>
      <TabsList>
        {list.map((m) => (
          <TabsTrigger key={m.id} value={m.id}>
            {m.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {list.map((m) => (
        <TabsContent key={m.id} value={m.id} className="pt-4">
          <ManagerPanel manager={m} />
        </TabsContent>
      ))}
    </Tabs>
  )
}
