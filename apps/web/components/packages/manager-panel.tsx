"use client"

import * as React from "react"
import {
  ArrowUpCircleIcon,
  CircleAlertIcon,
  DownloadIcon,
  InfoIcon,
  RefreshCwIcon,
  SearchIcon,
  Trash2Icon,
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
import { Button } from "@workspace/ui/components/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Input } from "@workspace/ui/components/input"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"
import { toast } from "@workspace/ui/components/toast"

import { JobDialog } from "@/components/job-dialog"

type Manager = Schemas["ManagerOut"]
type Job = Schemas["JobOut"]
type Installed = Schemas["InstalledPackage"]
type Upgradable = Schemas["UpgradablePackage"]
type Found = Schemas["PackageRef"]

const SHOWN = 200 // rows rendered at once; apt systems list thousands of packages

type Load<T> = { data: T | null; error: string | null; loading: boolean }

function useList<T>(fetcher: () => Promise<{ data?: T; error?: unknown }>) {
  const [state, setState] = React.useState<Load<T>>({
    data: null,
    error: null,
    loading: true,
  })
  const ref = React.useRef(fetcher)
  ref.current = fetcher
  const load = React.useCallback(async () => {
    setState((s) => ({ ...s, loading: true }))
    const { data, error } = await ref.current()
    setState({
      data: data ?? null,
      error: data ? null : errorMessage(error),
      loading: false,
    })
  }, [])
  React.useEffect(() => {
    void load()
  }, [load])
  return { ...state, load }
}

function PackageName({ name, title }: { name: string; title?: string | null }) {
  // Show the id under the title only when it says something new ("J" vs "j" doesn't).
  const showId = title && title.toLowerCase() !== name.toLowerCase()
  return (
    <div className="flex min-w-0 flex-col">
      <span className="truncate font-medium">{title ?? name}</span>
      {showId ? (
        <span className="truncate font-mono text-xs text-muted-foreground">
          {name}
        </span>
      ) : null}
    </div>
  )
}

/** "formula" is Homebrew's default and says nothing; casks, remotes and buckets do. */
function sourceBadge(source?: string | null) {
  return source && source !== "formula" ? source : null
}

function ListError({ error }: { error: string }) {
  return (
    <Alert variant="destructive">
      <CircleAlertIcon />
      <AlertTitle>Couldn&apos;t read the package list</AlertTitle>
      <AlertDescription className="font-mono text-xs break-all">
        {error}
      </AlertDescription>
    </Alert>
  )
}

function Confirm({
  open,
  title,
  description,
  action,
  destructive,
  onCancel,
  onConfirm,
}: {
  open: boolean
  title: string
  description: string
  action: string
  destructive?: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant={destructive ? "destructive" : "default"}
            onClick={onConfirm}
          >
            {action}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

type Pending =
  { kind: "uninstall"; name: string } | { kind: "upgrade-all" } | null

/** One package manager: installed packages, available updates, and search. */
export function ManagerPanel({ manager }: { manager: Manager }) {
  const id = manager.id
  const path = { params: { path: { manager: id } } }
  const installed = useList<Installed[]>(() =>
    api.GET("/api/packages/{manager}/installed", path)
  )
  const updates = useList<Upgradable[]>(() =>
    api.GET("/api/packages/{manager}/upgradable", path)
  )
  const [job, setJob] = React.useState<Job | null>(null)
  const [pending, setPending] = React.useState<Pending>(null)
  const [filter, setFilter] = React.useState("")
  const [query, setQuery] = React.useState("")
  const [results, setResults] = React.useState<Found[] | null>(null)
  const [searching, setSearching] = React.useState(false)
  const [searchError, setSearchError] = React.useState<string | null>(null)
  const lastQuery = React.useRef("")

  const started = (result: { data?: Job; error?: unknown }, what: string) => {
    if (result.data) setJob(result.data)
    else
      toast.add({
        type: "error",
        title: `Couldn't ${what}`,
        description: errorMessage(result.error),
      })
  }

  async function runSearch(q: string) {
    setSearching(true)
    setSearchError(null)
    lastQuery.current = q
    const { data, error } = await api.GET("/api/packages/{manager}/search", {
      params: { path: { manager: id }, query: { q } },
    })
    setSearching(false)
    if (data) setResults(data)
    else {
      setResults(null)
      setSearchError(errorMessage(error))
    }
  }

  const install = async (pkg: Found) =>
    started(
      await api.POST("/api/packages/{manager}/install", {
        ...path,
        body: { name: pkg.name, source: pkg.source ?? null },
      }),
      `install ${pkg.name}`
    )
  const uninstall = async (name: string) =>
    started(
      await api.POST("/api/packages/{manager}/uninstall", {
        ...path,
        body: { name },
      }),
      `uninstall ${name}`
    )
  const upgrade = async (name: string | null) =>
    started(
      await api.POST("/api/packages/{manager}/upgrade", {
        ...path,
        body: { name },
      }),
      name ? `upgrade ${name}` : "upgrade packages"
    )
  const refresh = async () =>
    started(
      await api.POST("/api/packages/{manager}/refresh", path),
      "refresh the package lists"
    )

  const afterJob = React.useCallback(() => {
    void installed.load()
    void updates.load()
    if (lastQuery.current) void runSearch(lastQuery.current)
    // runSearch only reads state setters and the stable manager id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [installed.load, updates.load])

  if (!manager.available) {
    return (
      <Alert>
        <InfoIcon />
        <AlertTitle>{manager.label} can&apos;t be used right now</AlertTitle>
        <AlertDescription>
          {manager.detail ?? "It isn't ready on this host."}
        </AlertDescription>
      </Alert>
    )
  }

  const upgradeByName = new Map(
    (updates.data ?? []).map((u) => [u.name, u] as const)
  )
  const needle = filter.trim().toLowerCase()
  const filtered = (installed.data ?? []).filter(
    (p) =>
      !needle ||
      p.name.toLowerCase().includes(needle) ||
      (p.title ?? "").toLowerCase().includes(needle) ||
      (p.description ?? "").toLowerCase().includes(needle)
  )
  const updateCount = updates.data?.length ?? 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm text-muted-foreground">
          {manager.detail}
        </p>
        {manager.can_refresh ? (
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCwIcon data-icon="inline-start" />
            Refresh lists
          </Button>
        ) : null}
        <Button
          size="sm"
          disabled={updateCount === 0}
          onClick={() => setPending({ kind: "upgrade-all" })}
        >
          <ArrowUpCircleIcon data-icon="inline-start" />
          Upgrade all
        </Button>
      </div>
      {manager.note ? (
        <Alert>
          <InfoIcon />
          <AlertDescription>{manager.note}</AlertDescription>
        </Alert>
      ) : null}

      <Tabs defaultValue="installed">
        <TabsList>
          <TabsTrigger value="installed">
            Installed
            {installed.data ? (
              <Badge variant="secondary">{installed.data.length}</Badge>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="updates">
            Updates
            {updateCount ? <Badge>{updateCount}</Badge> : null}
          </TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
        </TabsList>

        <TabsContent value="installed" className="flex flex-col gap-3 pt-2">
          <Input
            aria-label="Filter installed packages"
            placeholder="Filter installed packages"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="sm:max-w-xs"
          />
          {installed.error ? (
            <ListError error={installed.error} />
          ) : !installed.data ? (
            <Skeleton className="h-40 w-full" />
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {needle ? "No installed package matches." : "Nothing installed."}
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Package</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Description
                    </TableHead>
                    <TableHead className="w-0" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.slice(0, SHOWN).map((p) => {
                    const up = upgradeByName.get(p.name)
                    // winget shortens long ids in its table; a shortened id can't be
                    // passed back to it, so those rows can't be acted on here.
                    const shortened = p.name.endsWith("…")
                    return (
                      <TableRow key={`${p.source ?? ""}/${p.name}`}>
                        <TableCell className="max-w-56">
                          <PackageName name={p.name} title={p.title} />
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {/* The badge wraps under the version on narrow screens,
                              so the row actions stay in view. */}
                          <div className="flex flex-wrap items-center gap-1">
                            <span>{p.version}</span>
                            {up?.latest ? (
                              <Badge variant="outline">→ {up.latest}</Badge>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="hidden max-w-md truncate text-muted-foreground md:table-cell">
                          {p.description}
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            {up && manager.can_upgrade_one && !shortened ? (
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Upgrade ${p.name}`}
                                title="Upgrade"
                                onClick={() => upgrade(p.name)}
                              >
                                <ArrowUpCircleIcon />
                              </Button>
                            ) : null}
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Uninstall ${p.name}`}
                              disabled={shortened}
                              title={
                                shortened
                                  ? `${manager.label} shortened this id, so it can't be uninstalled from here`
                                  : "Uninstall"
                              }
                              onClick={() =>
                                setPending({ kind: "uninstall", name: p.name })
                              }
                            >
                              <Trash2Icon />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              {filtered.length > SHOWN ? (
                <p className="text-sm text-muted-foreground">
                  Showing {SHOWN} of {filtered.length}. Filter to narrow down.
                </p>
              ) : null}
            </>
          )}
        </TabsContent>

        <TabsContent value="updates" className="flex flex-col gap-3 pt-2">
          {updates.error ? (
            <ListError error={updates.error} />
          ) : !updates.data ? (
            <Skeleton className="h-24 w-full" />
          ) : updates.data.length === 0 ? (
            <Empty className="border py-8">
              <EmptyHeader>
                <EmptyTitle>Everything is up to date</EmptyTitle>
                <EmptyDescription>
                  {manager.can_refresh
                    ? "As of the last list refresh. Refresh lists to check again."
                    : "Nothing to upgrade."}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Package</TableHead>
                  <TableHead>Installed</TableHead>
                  <TableHead>Available</TableHead>
                  <TableHead className="w-0" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {updates.data.slice(0, SHOWN).map((u) => (
                  <TableRow key={u.name}>
                    <TableCell className="max-w-56 truncate font-medium">
                      {u.name}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {u.version ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {u.latest ?? "—"}
                    </TableCell>
                    <TableCell>
                      {manager.can_upgrade_one ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => upgrade(u.name)}
                        >
                          Upgrade
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="search" className="flex flex-col gap-3 pt-2">
          <form
            className="flex gap-2 sm:max-w-md"
            onSubmit={(e) => {
              e.preventDefault()
              if (query.trim()) void runSearch(query.trim())
            }}
          >
            <Input
              aria-label={`Search ${manager.label}`}
              placeholder={`Search ${manager.label}`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Button type="submit" disabled={!query.trim() || searching}>
              <SearchIcon data-icon="inline-start" />
              Search
            </Button>
          </form>
          {searchError ? (
            <ListError error={searchError} />
          ) : searching ? (
            <Skeleton className="h-40 w-full" />
          ) : results === null ? null : results.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No packages match &ldquo;{lastQuery.current}&rdquo;.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Package</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead className="hidden md:table-cell">
                    Description
                  </TableHead>
                  <TableHead className="w-0" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((r) => (
                  <TableRow key={`${r.source ?? ""}/${r.name}`}>
                    <TableCell className="max-w-56">
                      <PackageName name={r.name} title={r.title} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {r.version}
                      {sourceBadge(r.source) ? (
                        <Badge variant="outline" className="ml-2">
                          {sourceBadge(r.source)}
                        </Badge>
                      ) : null}
                    </TableCell>
                    <TableCell className="hidden max-w-md truncate text-muted-foreground md:table-cell">
                      {r.description}
                    </TableCell>
                    <TableCell>
                      {r.installed ? (
                        <Badge variant="secondary">Installed</Badge>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => install(r)}
                        >
                          <DownloadIcon data-icon="inline-start" />
                          Install
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>
      </Tabs>

      <Confirm
        open={pending?.kind === "uninstall"}
        title={`Uninstall ${pending?.kind === "uninstall" ? pending.name : ""}?`}
        description="It's removed from this server. Packages that depend on it may be removed too."
        action="Uninstall"
        destructive
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (pending?.kind === "uninstall") void uninstall(pending.name)
          setPending(null)
        }}
      />
      <Confirm
        open={pending?.kind === "upgrade-all"}
        title={`Upgrade all ${manager.label} packages?`}
        description={`${updateCount} package${updateCount === 1 ? "" : "s"} will be upgraded. This can take a while.`}
        action="Upgrade all"
        onCancel={() => setPending(null)}
        onConfirm={() => {
          void upgrade(null)
          setPending(null)
        }}
      />
      <JobDialog job={job} onClose={() => setJob(null)} onFinished={afterJob} />
    </div>
  )
}
