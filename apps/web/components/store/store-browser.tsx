"use client"

import * as React from "react"
import Link from "next/link"
import { SearchIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Badge } from "@workspace/ui/components/badge"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@workspace/ui/components/input-group"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@workspace/ui/components/toggle-group"

import { AppIcon } from "@/components/store/app-icon"

type StoreApp = Schemas["StoreApp"]
type Category = Schemas["Category"]

export function storeAppHref(app: { catalog: string; id: string }) {
  return `/store/view/?catalog=${encodeURIComponent(app.catalog)}&id=${encodeURIComponent(app.id)}`
}

export function StoreBrowser() {
  const [apps, setApps] = React.useState<StoreApp[] | null>(null)
  const [categories, setCategories] = React.useState<Category[]>([])
  const [error, setError] = React.useState<string | null>(null)
  const [query, setQuery] = React.useState("")
  const [category, setCategory] = React.useState<string>("all")

  React.useEffect(() => {
    void Promise.all([
      api.GET("/api/store/apps"),
      api.GET("/api/store/categories"),
    ]).then(([appsRes, catsRes]) => {
      if (appsRes.data) setApps(appsRes.data)
      else setError(errorMessage(appsRes.error, "Couldn't load the store"))
      if (catsRes.data) setCategories(catsRes.data)
    })
  }, [])

  const labels = React.useMemo(
    () => Object.fromEntries(categories.map((c) => [c.id, c.label])),
    [categories]
  )

  const shown = React.useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (apps ?? []).filter(
      (a) =>
        (category === "all" || a.category === category) &&
        (!needle ||
          a.title.toLowerCase().includes(needle) ||
          a.description.toLowerCase().includes(needle))
    )
  }, [apps, query, category])

  if (error && !apps) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>Couldn&apos;t load the store</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <InputGroup className="max-w-md">
        <InputGroupAddon>
          <SearchIcon />
        </InputGroupAddon>
        <InputGroupInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search apps"
          aria-label="Search apps"
        />
      </InputGroup>

      <ToggleGroup
        value={[category]}
        onValueChange={(value: string[]) => setCategory(value[0] ?? "all")}
        variant="outline"
        size="sm"
        spacing={2}
        className="flex-wrap"
      >
        <ToggleGroupItem value="all">All</ToggleGroupItem>
        {categories.map((c) => (
          <ToggleGroupItem key={c.id} value={c.id}>
            {c.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {!apps ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>No apps match</EmptyTitle>
            <EmptyDescription>Try another search or category.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((app) => (
            <Link
              key={`${app.catalog}/${app.id}`}
              href={storeAppHref(app)}
              className="rounded-xl focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              <Card className="h-full transition-colors hover:bg-muted/40">
                <CardHeader className="grid-cols-[auto_1fr] items-start gap-x-3">
                  <AppIcon
                    title={app.title}
                    icon={app.icon}
                    className="row-span-2"
                  />
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    {app.title}
                    {app.installed.length ? (
                      <Badge variant="secondary">Installed</Badge>
                    ) : null}
                  </CardTitle>
                  <CardDescription className="line-clamp-2">
                    {app.description}
                  </CardDescription>
                  <div className="col-start-2 pt-1">
                    <Badge variant="outline">
                      {labels[app.category] ?? app.category}
                    </Badge>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
