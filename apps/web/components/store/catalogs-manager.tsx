"use client"

import * as React from "react"
import { PlusIcon, RefreshCwIcon, Trash2Icon } from "lucide-react"

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
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemTitle,
} from "@workspace/ui/components/item"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { toast } from "@workspace/ui/components/toast"

import { JobDialog } from "@/components/job-dialog"

type CatalogOut = Schemas["CatalogOut"]
type Job = Schemas["JobOut"]
type Kind = "auto" | "athena" | "casaos"

const KINDS: { label: string; value: Kind }[] = [
  { label: "Detect automatically", value: "auto" },
  { label: "Athena catalog", value: "athena" },
  { label: "CasaOS AppStore", value: "casaos" },
]

/** The official CasaOS AppStore release archive (Apache-2.0, ~1.5 MB, 180+ apps). */
const CASAOS = {
  name: "CasaOS AppStore",
  url: "https://github.com/IceWhaleTech/CasaOS-AppStore/releases/latest/download/main.zip",
  kind: "casaos" as Kind,
}

function when(iso: string | null | undefined) {
  return iso ? new Date(iso).toLocaleString() : "never"
}

export function CatalogsManager() {
  const [catalogs, setCatalogs] = React.useState<CatalogOut[] | null>(null)
  const [job, setJob] = React.useState<Job | null>(null)
  const [removing, setRemoving] = React.useState<CatalogOut | null>(null)
  const [name, setName] = React.useState("")
  const [url, setUrl] = React.useState("")
  const [kind, setKind] = React.useState<Kind>("auto")

  const load = React.useCallback(async () => {
    const { data } = await api.GET("/api/store/catalogs")
    if (data) setCatalogs(data)
  }, [])
  React.useEffect(() => void load(), [load])

  async function add(body: { name: string; url: string; kind: Kind }) {
    const { data, error } = await api.POST("/api/store/catalogs", { body })
    if (data) {
      setJob(data)
      setName("")
      setUrl("")
      void load()
    } else {
      toast.add({
        type: "error",
        title: "Couldn't add the catalog",
        description: errorMessage(error),
      })
    }
  }

  async function refresh(c: CatalogOut) {
    const { data, error } = await api.POST(
      "/api/store/catalogs/{catalog_id}/refresh",
      { params: { path: { catalog_id: c.id } } }
    )
    if (data) setJob(data)
    else
      toast.add({
        type: "error",
        title: `Couldn't refresh ${c.name}`,
        description: errorMessage(error),
      })
  }

  async function remove(c: CatalogOut) {
    setRemoving(null)
    const { error } = await api.DELETE("/api/store/catalogs/{catalog_id}", {
      params: { path: { catalog_id: c.id } },
    })
    if (error)
      toast.add({
        type: "error",
        title: `Couldn't remove ${c.name}`,
        description: errorMessage(error),
      })
    else toast.add({ type: "success", title: `Removed ${c.name}` })
    void load()
  }

  const hasCasaOS = catalogs?.some((c) => c.url === CASAOS.url)

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_minmax(0,26rem)]">
      <div className="flex flex-col gap-4">
        {!catalogs ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <ItemGroup className="gap-2">
            {catalogs.map((c) => (
              <Item key={c.id} variant="outline">
                <ItemContent>
                  <ItemTitle>
                    {c.name}
                    {c.builtin ? (
                      <Badge variant="secondary">Built in</Badge>
                    ) : null}
                    {c.error ? (
                      <Badge variant="destructive">Refresh failed</Badge>
                    ) : null}
                  </ItemTitle>
                  <ItemDescription>
                    {c.app_count} apps
                    {c.builtin
                      ? " · ships with Athena"
                      : ` · updated ${when(c.refreshed_at)}`}
                  </ItemDescription>
                  {c.url ? (
                    <ItemDescription className="font-mono text-xs break-all">
                      {c.url}
                    </ItemDescription>
                  ) : null}
                  {c.error ? (
                    <ItemDescription className="text-destructive">
                      {c.error}
                    </ItemDescription>
                  ) : null}
                </ItemContent>
                {!c.builtin ? (
                  <ItemActions>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => refresh(c)}
                    >
                      <RefreshCwIcon data-icon="inline-start" />
                      Refresh
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setRemoving(c)}
                    >
                      <Trash2Icon />
                      <span className="sr-only">Remove {c.name}</span>
                    </Button>
                  </ItemActions>
                ) : null}
              </Item>
            ))}
          </ItemGroup>
        )}
      </div>

      <div className="flex flex-col gap-4">
        {!hasCasaOS ? (
          <Card>
            <CardHeader>
              <CardTitle>CasaOS AppStore</CardTitle>
              <CardDescription>
                Over 180 community apps, converted to Athena&apos;s format.
                Apache-2.0.
              </CardDescription>
            </CardHeader>
            <CardFooter>
              <Button onClick={() => add(CASAOS)}>
                <PlusIcon data-icon="inline-start" />
                Add CasaOS AppStore
              </Button>
            </CardFooter>
          </Card>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Add a catalog</CardTitle>
            <CardDescription>
              A GitHub, Codeberg or GitLab repository, or a direct .tar.gz/.zip
              link.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                void add({ name, url, kind })
              }}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="catalog-name">Name</FieldLabel>
                  <Input
                    id="catalog-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="My apps"
                    required
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="catalog-url">URL</FieldLabel>
                  <Input
                    id="catalog-url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://github.com/you/athena-apps"
                    type="url"
                    required
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="catalog-kind">Format</FieldLabel>
                  <Select
                    items={KINDS}
                    value={kind}
                    onValueChange={(v) => setKind((v as Kind) ?? "auto")}
                  >
                    <SelectTrigger id="catalog-kind">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {KINDS.map((k) => (
                          <SelectItem key={k.value} value={k.value}>
                            {k.label}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                  <FieldDescription>
                    Athena catalogs use apps/&lt;id&gt;/compose.yaml; CasaOS
                    stores use Apps/&lt;Name&gt;/docker-compose.yml.
                  </FieldDescription>
                </Field>
                <Field>
                  <Button type="submit" disabled={!name.trim() || !url.trim()}>
                    <PlusIcon data-icon="inline-start" />
                    Add catalog
                  </Button>
                </Field>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>
      </div>

      <JobDialog
        job={job}
        onClose={() => setJob(null)}
        onFinished={() => void load()}
      />
      <AlertDialog
        open={removing !== null}
        onOpenChange={(o) => !o && setRemoving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its apps disappear from the store. Apps you already installed from
              it keep running.
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
    </div>
  )
}
