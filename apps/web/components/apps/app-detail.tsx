"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import {
  PlayIcon,
  RefreshCcwIcon,
  RotateCwIcon,
  SaveIcon,
  ScrollTextIcon,
  SquareIcon,
  Trash2Icon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { CodeEditor } from "@workspace/ui/components/athena/code-editor"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { FieldDescription } from "@workspace/ui/components/field"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemTitle,
} from "@workspace/ui/components/item"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"

import {
  AppStatusBadge,
  DeleteAppDialog,
  OpenLinks,
} from "@/components/apps/app-bits"
import { useAppJobs } from "@/components/apps/use-app-jobs"
import { LogsSheet } from "@/components/containers/logs-sheet"

type AppDetailOut = Schemas["AppDetail"]
type Container = Schemas["ContainerOut"]

export function AppDetail({ name }: { name: string }) {
  const router = useRouter()
  const [app, setApp] = React.useState<AppDetailOut | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [draft, setDraft] = React.useState<string | null>(null)
  const [envDraft, setEnvDraft] = React.useState<string | null>(null)
  const [logsFor, setLogsFor] = React.useState<Container | null>(null)
  const [removing, setRemoving] = React.useState(false)
  const removed = React.useRef(false)

  const load = React.useCallback(async () => {
    const { data, error: err } = await api.GET("/api/apps/{name}", {
      params: { path: { name } },
    })
    if (data) {
      setApp(data)
      setError(null)
    } else setError(errorMessage(err, "Couldn't load the app"))
  }, [name])

  React.useEffect(() => {
    void load()
    const timer = window.setInterval(load, 10_000)
    return () => window.clearInterval(timer)
  }, [load])

  const jobs = useAppJobs((ok) => {
    if (removed.current && ok) router.push("/apps/")
    else {
      setDraft(null)
      setEnvDraft(null)
      void load()
    }
  })

  if (error && !app) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>Couldn&apos;t load {name}</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  if (!app) return <Skeleton className="h-64 w-full" />

  const dirty = draft !== null && draft !== app.compose
  const envDirty = envDraft !== null && envDraft !== app.env

  async function saveEnv() {
    if (envDraft === null) return
    jobs.show(
      await api.PUT("/api/apps/{name}/env", {
        params: { path: { name } },
        body: { env: envDraft },
      }),
      `save ${name} settings`
    )
  }

  async function save() {
    if (draft === null) return
    jobs.show(
      await api.PUT("/api/apps/{name}", {
        params: { path: { name } },
        body: { compose: draft },
      }),
      `save ${name}`
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">{app.name}</h2>
        <AppStatusBadge app={app} />
        <div className="flex flex-wrap gap-2 md:ml-auto">
          <OpenLinks app={app} />
          {app.status === "running" ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => jobs.action(name, "restart")}
              >
                <RotateCwIcon data-icon="inline-start" />
                Restart
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => jobs.action(name, "stop")}
              >
                <SquareIcon data-icon="inline-start" />
                Stop
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => jobs.action(name, "start")}>
              <PlayIcon data-icon="inline-start" />
              Start
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => jobs.action(name, "update")}
          >
            <RefreshCcwIcon data-icon="inline-start" />
            Update images
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setRemoving(true)}
          >
            <Trash2Icon data-icon="inline-start" />
            Remove
          </Button>
        </div>
      </div>

      <Tabs defaultValue="containers">
        <TabsList>
          <TabsTrigger value="containers">
            Containers <Badge variant="secondary">{app.total}</Badge>
          </TabsTrigger>
          <TabsTrigger value="compose">Compose</TabsTrigger>
          {app.env !== null ? (
            <TabsTrigger value="settings">Settings</TabsTrigger>
          ) : null}
        </TabsList>

        <TabsContent value="containers" className="pt-2">
          {app.containers.length === 0 ? (
            <Empty className="border">
              <EmptyHeader>
                <EmptyTitle>No containers</EmptyTitle>
                <EmptyDescription>
                  Start the app to create its containers.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ItemGroup className="gap-2">
              {app.containers.map((c) => (
                <Item key={c.id} variant="outline">
                  <ItemContent>
                    <ItemTitle>
                      {c.service ?? c.name}
                      <Badge
                        variant={
                          c.state === "running" ? "secondary" : "outline"
                        }
                        className="capitalize"
                      >
                        {c.state}
                      </Badge>
                    </ItemTitle>
                    <ItemDescription>
                      {c.image}
                      {c.ports.length ? ` · ${c.ports.join(", ")}` : ""}
                    </ItemDescription>
                  </ItemContent>
                  <ItemActions>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setLogsFor(c)}
                    >
                      <ScrollTextIcon data-icon="inline-start" />
                      Logs
                    </Button>
                  </ItemActions>
                </Item>
              ))}
            </ItemGroup>
          )}
        </TabsContent>

        <TabsContent value="compose" className="flex flex-col gap-3 pt-2">
          <CodeEditor
            value={draft ?? app.compose}
            onChange={setDraft}
            aria-label={`${app.name} compose.yaml`}
            minHeight="20rem"
          />
          <FieldDescription>
            Saving keeps the previous version as compose.prev.yaml and redeploys
            the app.
          </FieldDescription>
          <div className="flex gap-2">
            <Button onClick={save} disabled={!dirty}>
              <SaveIcon data-icon="inline-start" />
              Save and redeploy
            </Button>
            <Button
              variant="outline"
              onClick={() => setDraft(null)}
              disabled={!dirty}
            >
              Discard changes
            </Button>
          </div>
        </TabsContent>

        {app.env !== null ? (
          <TabsContent value="settings" className="flex flex-col gap-3 pt-2">
            <CodeEditor
              value={envDraft ?? app.env ?? ""}
              onChange={setEnvDraft}
              language="text"
              aria-label={`${app.name} .env`}
              minHeight="12rem"
            />
            <FieldDescription>
              The values from the install form (.env). Change a port or folder
              here, then save to redeploy. It may contain generated passwords.
            </FieldDescription>
            <div className="flex gap-2">
              <Button onClick={saveEnv} disabled={!envDirty}>
                <SaveIcon data-icon="inline-start" />
                Save and redeploy
              </Button>
              <Button
                variant="outline"
                onClick={() => setEnvDraft(null)}
                disabled={!envDirty}
              >
                Discard changes
              </Button>
            </div>
          </TabsContent>
        ) : null}
      </Tabs>

      <LogsSheet container={logsFor} onClose={() => setLogsFor(null)} />
      <DeleteAppDialog
        name={removing ? name : null}
        onCancel={() => setRemoving(false)}
        onConfirm={(deleteData) => {
          setRemoving(false)
          removed.current = true
          void jobs.remove(name, deleteData)
        }}
      />
      {jobs.dialog}
    </div>
  )
}
