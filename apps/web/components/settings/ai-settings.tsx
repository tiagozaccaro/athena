"use client"

import * as React from "react"
import {
  ChevronDownIcon,
  CloudIcon,
  CpuIcon,
  PencilIcon,
  PlugZapIcon,
  PlusIcon,
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
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
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
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import { ModelPicker } from "@/components/assistant/model-picker"
import { useModels, type ModelRef } from "@/components/assistant/use-models"
import { useAuth } from "@/components/auth-provider"
import { useCapability } from "@/components/capabilities-provider"
import {
  ProviderDialog,
  type Provider,
  type ProviderEditing,
  type ProviderKind,
} from "@/components/settings/ai-provider-dialog"

type AiSettings = Schemas["AiSettings"]

function AddMenu({
  kinds,
  onPick,
  label = "Add provider",
}: {
  kinds: ProviderKind[]
  onPick: (kind: ProviderKind) => void
  label?: string
}) {
  const groups: [string, ProviderKind[]][] = [
    ["Cloud", kinds.filter((k) => k.group === "cloud")],
    ["Local", kinds.filter((k) => k.group === "local")],
  ]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>
        <PlusIcon />
        {label}
        <ChevronDownIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        {groups.map(([title, list], i) => (
          <React.Fragment key={title}>
            {i > 0 ? <DropdownMenuSeparator /> : null}
            <DropdownMenuGroup>
              <DropdownMenuLabel>{title}</DropdownMenuLabel>
              {list.map((k) => (
                <DropdownMenuItem key={k.id} onClick={() => onPick(k)}>
                  {k.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </React.Fragment>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ProvidersCard({ onChanged }: { onChanged: () => void }) {
  const ollama = useCapability("ai.ollama")
  const [kinds, setKinds] = React.useState<ProviderKind[]>([])
  const [providers, setProviders] = React.useState<Provider[] | null>(null)
  const [editing, setEditing] = React.useState<ProviderEditing>(null)
  const [removing, setRemoving] = React.useState<Provider | null>(null)
  const [testing, setTesting] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    const { data } = await api.GET("/api/assistant/providers")
    setProviders(data ?? [])
  }, [])

  React.useEffect(() => {
    void api
      .GET("/api/assistant/kinds")
      .then(({ data }) => setKinds(data ?? []))
    void load()
  }, [load])

  const kindOf = (id: string) => kinds.find((k) => k.id === id)
  const ollamaKind = kindOf("ollama")

  async function test(p: Provider) {
    setTesting(p.id)
    const { data, error } = await api.POST(
      "/api/assistant/providers/{provider_id}/test",
      {
        params: { path: { provider_id: p.id } },
      }
    )
    setTesting(null)
    if (data?.ok)
      toast.add({ type: "success", title: p.name, description: data.message })
    else
      toast.add({
        type: "error",
        title: `${p.name} didn't connect`,
        description: data?.message ?? errorMessage(error),
      })
  }

  async function remove(p: Provider) {
    setRemoving(null)
    const { error } = await api.DELETE(
      "/api/assistant/providers/{provider_id}",
      {
        params: { path: { provider_id: p.id } },
      }
    )
    if (error) {
      toast.add({
        type: "error",
        title: "Couldn't remove",
        description: errorMessage(error),
      })
      return
    }
    await load()
    onChanged()
  }

  async function saved(p: Provider) {
    const added = !editing?.provider
    setEditing(null)
    await load()
    onChanged()
    if (added) void test(p)
  }

  function useOllama() {
    if (!ollamaKind || !ollama?.endpoint) return
    setEditing({ kind: ollamaKind, values: { base_url: ollama.endpoint } })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Providers</CardTitle>
        <CardDescription>
          Set up providers once, then pick any of their models in a chat.
        </CardDescription>
        {providers?.length ? (
          <CardAction>
            <AddMenu kinds={kinds} onPick={(kind) => setEditing({ kind })} />
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>
        {providers === null ? (
          <Skeleton className="h-16 w-full" />
        ) : providers.length === 0 ? (
          <Empty className="border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                {ollama?.available ? <CpuIcon /> : <CloudIcon />}
              </EmptyMedia>
              <EmptyTitle>No providers yet</EmptyTitle>
              <EmptyDescription>
                {ollama?.available
                  ? `${ollama.detail ?? "Ollama"} is running on this server. Its models run on your own hardware and nothing leaves the server.`
                  : "Add a cloud provider with an API key, or install Ollama on this server to run models locally."}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent className="flex-row flex-wrap justify-center">
              {ollama?.available && ollamaKind ? (
                <Button onClick={useOllama}>
                  <CpuIcon />
                  Use Ollama on this server
                </Button>
              ) : null}
              <AddMenu
                kinds={kinds}
                onPick={(kind) => setEditing({ kind })}
                label={
                  ollama?.available
                    ? "Another provider"
                    : "Add a cloud provider"
                }
              />
            </EmptyContent>
          </Empty>
        ) : (
          <ItemGroup className="gap-2">
            {providers.map((p) => (
              <Item key={p.id} variant="outline" size="sm">
                <ItemContent>
                  <ItemTitle>{p.name}</ItemTitle>
                  <ItemDescription>
                    {kindOf(p.kind)?.label ?? p.kind}
                    {p.values.base_url ? ` · ${p.values.base_url}` : ""}
                  </ItemDescription>
                </ItemContent>
                <ItemActions>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void test(p)}
                    disabled={testing === p.id}
                  >
                    {testing === p.id ? <Spinner /> : <PlugZapIcon />}
                    Test
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Edit ${p.name}`}
                    onClick={() => {
                      const kind = kindOf(p.kind)
                      if (kind) setEditing({ kind, provider: p })
                    }}
                  >
                    <PencilIcon />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Remove ${p.name}`}
                    onClick={() => setRemoving(p)}
                  >
                    <Trash2Icon />
                  </Button>
                </ItemActions>
              </Item>
            ))}
          </ItemGroup>
        )}
      </CardContent>
      <ProviderDialog
        editing={editing}
        onClose={() => setEditing(null)}
        onSaved={saved}
      />
      <AlertDialog
        open={removing !== null}
        onOpenChange={(o) => !o && setRemoving(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its key is deleted from this server. Chats that used its models
              stay, and ask for another model.
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
    </Card>
  )
}

function DefaultsCard({ version }: { version: number }) {
  const { providers, reload } = useModels()
  const [settings, setSettings] = React.useState<AiSettings | null>(null)
  const [limit, setLimit] = React.useState("")

  React.useEffect(() => {
    void api.GET("/api/settings/ai").then(({ data }) => {
      if (!data) return
      setSettings(data)
      setLimit(data.spend_limit_usd ? String(data.spend_limit_usd) : "")
    })
    if (version > 0) void reload()
  }, [version, reload])

  async function save(next: AiSettings, message: string) {
    const previous = settings
    setSettings(next)
    const { data, error } = await api.PUT("/api/settings/ai", { body: next })
    if (data) {
      setSettings(data)
      toast.add({ type: "success", title: message })
    } else {
      setSettings(previous)
      toast.add({
        type: "error",
        title: "Couldn't save",
        description: errorMessage(error),
      })
    }
  }

  function saveLimit() {
    if (!settings) return
    const value = limit.trim() === "" ? null : Number(limit)
    if (value !== null && (!Number.isFinite(value) || value <= 0)) {
      toast.add({
        type: "error",
        title: "Enter an amount above 0, or leave it empty",
      })
      return
    }
    if (value === (settings.spend_limit_usd ?? null)) return
    void save(
      { ...settings, spend_limit_usd: value },
      value ? `Chats stop at $${value}` : "No spend limit"
    )
  }

  if (!providers?.length && settings !== null) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Defaults</CardTitle>
        <CardDescription>
          New chats start with the default model. Each chat can switch model at
          any time.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="default-model">Default model</FieldLabel>
              <ModelPicker
                id="default-model"
                variant="field"
                providers={providers}
                value={settings.default_model}
                onChange={(ref: ModelRef) =>
                  void save(
                    { ...settings, default_model: ref },
                    "Default model saved"
                  )
                }
              />
              <FieldDescription>
                Only models that can use tools work with the assistant.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="title-model">
                Model for chat titles
              </FieldLabel>
              <ModelPicker
                id="title-model"
                variant="field"
                providers={providers}
                value={settings.title_model}
                onChange={(ref: ModelRef) =>
                  void save(
                    { ...settings, title_model: ref },
                    "Title model saved"
                  )
                }
              />
              <FieldDescription>
                Optional. A small, cheap model is enough.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="spend-limit">
                Spend limit per chat (USD)
              </FieldLabel>
              <Input
                id="spend-limit"
                inputMode="decimal"
                value={limit}
                placeholder="No limit"
                onChange={(e) => setLimit(e.target.value)}
                onBlur={saveLimit}
                onKeyDown={(e) => e.key === "Enter" && saveLimit()}
                className="max-w-40"
              />
              <FieldDescription>
                A chat stops once it has cost this much. Only applies to models
                with known prices; local models are free.
              </FieldDescription>
            </Field>
          </FieldGroup>
        )}
      </CardContent>
    </Card>
  )
}

/** Settings → AI: providers, default models and limits (admins only). */
export function AiSettingsView() {
  const { user } = useAuth()
  const [version, setVersion] = React.useState(0)
  if (!user.is_admin) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>Only admins can set up the assistant</EmptyTitle>
        </EmptyHeader>
      </Empty>
    )
  }
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <ProvidersCard onChanged={() => setVersion((v) => v + 1)} />
      <DefaultsCard version={version} />
    </div>
  )
}
