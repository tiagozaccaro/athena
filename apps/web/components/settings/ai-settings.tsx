"use client"

import * as React from "react"
import {
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
  Combobox,
  ComboboxCollection,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
  ComboboxTrigger,
} from "@workspace/ui/components/combobox"
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
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
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
import { Switch } from "@workspace/ui/components/switch"
import { Textarea } from "@workspace/ui/components/textarea"
import { toast } from "@workspace/ui/components/toast"

import { ModelPicker } from "@/components/assistant/model-picker"
import { useModels, type ModelRef } from "@/components/assistant/use-models"
import { useAuth } from "@/components/auth-provider"
import { useCapability } from "@/components/capabilities-provider"
import { IntegrationDialog } from "@/components/settings/ai-integration-dialog"
import {
  ProviderDialog,
  type Provider,
  type ProviderEditing,
  type ProviderKind,
} from "@/components/settings/ai-provider-dialog"
import {
  editingFor,
  LocalServerButtons,
  localServersSentence,
  useLocalAiServers,
} from "@/components/settings/local-ai-servers"

type AiSettings = Schemas["AiSettings"]
type Integration = Schemas["IntegrationOut"]
type IntegrationKind = Schemas["IntegrationKindOut"]

type KindGroup = { value: string; items: ProviderKind[] }

/**
 * A searchable "Add provider" picker: models.dev lists dozens of providers, too many
 * for a plain menu.
 */
export function AddMenu({
  kinds,
  onPick,
  label = "Add provider",
}: {
  kinds: ProviderKind[]
  onPick: (kind: ProviderKind) => void
  label?: string
}) {
  const groups = React.useMemo<KindGroup[]>(() => {
    const byLabel = (a: ProviderKind, b: ProviderKind) =>
      a.label.localeCompare(b.label)
    return [
      {
        value: "Cloud",
        items: kinds.filter((k) => k.group === "cloud").sort(byLabel),
      },
      {
        value: "Local",
        items: kinds.filter((k) => k.group === "local").sort(byLabel),
      },
      // Custom endpoints stay last, in the server's order.
      { value: "Custom", items: kinds.filter((k) => k.group === "custom") },
    ].filter((g) => g.items.length > 0)
  }, [kinds])
  return (
    <Combobox
      items={groups}
      value={null}
      onValueChange={(k: ProviderKind | null) => {
        if (k) onPick(k)
      }}
      itemToStringLabel={(k: ProviderKind) => k.label}
      itemToStringValue={(k: ProviderKind) => k.id}
    >
      <ComboboxTrigger render={<Button variant="outline" size="sm" />}>
        <PlusIcon />
        {label}
      </ComboboxTrigger>
      <ComboboxContent className="w-64 max-w-[calc(100vw-2rem)]" align="end">
        <ComboboxInput showTrigger={false} placeholder="Search providers" />
        <ComboboxEmpty>No provider matches.</ComboboxEmpty>
        <ComboboxList>
          {(group: KindGroup) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{group.value}</ComboboxLabel>
              <ComboboxCollection>
                {(k: ProviderKind) => (
                  <ComboboxItem key={k.id} value={k}>
                    {k.label}
                  </ComboboxItem>
                )}
              </ComboboxCollection>
            </ComboboxGroup>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  )
}

function ProvidersCard({ onChanged }: { onChanged: () => void }) {
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
  const local = useLocalAiServers(kinds)

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
                {local.length ? <CpuIcon /> : <CloudIcon />}
              </EmptyMedia>
              <EmptyTitle>No providers yet</EmptyTitle>
              <EmptyDescription>
                {local.length
                  ? localServersSentence(local)
                  : "Add a cloud provider with an API key, or run Ollama, llama.cpp or another local AI server on this server to run models locally."}
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent className="flex-row flex-wrap justify-center">
              <LocalServerButtons
                servers={local}
                onUse={(server) => setEditing(editingFor(server))}
              />
              <AddMenu
                kinds={kinds}
                onPick={(kind) => setEditing({ kind })}
                label={local.length ? "Another provider" : "Add a provider"}
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

type SaveAi = (next: AiSettings, message: string) => Promise<void>

/**
 * The AI settings row, shared by the cards so one card's save never undoes another's.
 * Reloaded when providers change (removing one can clear the default model).
 */
function useAiSettings(version: number) {
  const [settings, setSettings] = React.useState<AiSettings | null>(null)

  React.useEffect(() => {
    void api.GET("/api/settings/ai").then(({ data }) => {
      if (data) setSettings(data)
    })
  }, [version])

  const save = React.useCallback<SaveAi>(
    async (next, message) => {
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
    },
    [settings]
  )
  return { settings, save }
}

function DefaultsCard({
  version,
  settings,
  save,
}: {
  version: number
  settings: AiSettings | null
  save: SaveAi
}) {
  const { providers, reload } = useModels()
  const [limit, setLimit] = React.useState("")
  const savedLimit = settings?.spend_limit_usd

  React.useEffect(() => {
    setLimit(savedLimit ? String(savedLimit) : "")
  }, [savedLimit])

  React.useEffect(() => {
    if (version > 0) void reload()
  }, [version, reload])

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
              <FieldLabel htmlFor="advisor-model">Advisor model</FieldLabel>
              <div className="flex gap-2">
                <ModelPicker
                  id="advisor-model"
                  variant="field"
                  className="flex-1"
                  providers={providers}
                  value={settings.advisor_model}
                  onChange={(ref: ModelRef) =>
                    void save(
                      { ...settings, advisor_model: ref },
                      "Advisor model saved"
                    )
                  }
                />
                {settings.advisor_model && (
                  <Button
                    variant="outline"
                    onClick={() =>
                      void save(
                        { ...settings, advisor_model: null },
                        "Advisor turned off"
                      )
                    }
                  >
                    Turn off
                  </Button>
                )}
              </div>
              <FieldDescription>
                Optional. A stronger model the assistant can ask for a second
                opinion, once per step. Its provider sees the question the
                assistant writes, not the whole chat, and what it costs counts
                toward the spend limit.
              </FieldDescription>
            </Field>
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor="refine-answers">
                  Double-check answers
                </FieldLabel>
                <FieldDescription>
                  Before it finishes, the assistant reviews its answer and
                  writes it again, fixed. At least one more model request per
                  reply, so slower and costlier; the first draft stays folded in
                  the reply.
                </FieldDescription>
              </FieldContent>
              <Switch
                id="refine-answers"
                checked={settings.refine_answers}
                onCheckedChange={(checked) =>
                  void save(
                    { ...settings, refine_answers: checked },
                    checked
                      ? "Answers are double-checked"
                      : "Answers are no longer double-checked"
                  )
                }
              />
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

/** Splits what the admin typed into program names: spaces, commas or new lines. */
function parseCommands(text: string): string[] {
  return [...new Set(text.split(/[\s,]+/).filter(Boolean))]
}

function ShellCard({
  settings,
  save,
}: {
  settings: AiSettings | null
  save: SaveAi
}) {
  const where = useCapability("assistant.shell")
  const [text, setText] = React.useState("")
  const saved = settings
    ? (settings.shell_commands ?? []).join("\n")
    : undefined

  React.useEffect(() => {
    if (saved !== undefined) setText(saved)
  }, [saved])

  function saveCommands() {
    if (!settings) return
    const commands = parseCommands(text)
    const bad = commands.find((c) => /[;&|<>()`$]/.test(c))
    if (bad) {
      toast.add({
        type: "error",
        title: `“${bad}” isn't a program name`,
        description:
          "List programs only, one per line, without shell operators like ; | & > or $.",
      })
      return
    }
    if (commands.join("\n") === saved) {
      setText(saved)
      return
    }
    void save(
      { ...settings, shell_commands: commands },
      commands.length ? "Allowlist saved" : "Allowlist emptied"
    )
  }

  if (where?.status !== "ready") return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Shell</CardTitle>
        <CardDescription>
          Let the assistant ask to run commands on this server, as the user
          Athena runs as. You approve every command before it runs, and each one
          is written to the audit log.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <FieldGroup>
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor="shell-enabled">Assistant shell</FieldLabel>
                <FieldDescription>
                  Off by default. Athena&apos;s own tools (apps, packages,
                  files) don&apos;t need it.
                  {where.detail && ` ${where.detail}.`}
                </FieldDescription>
              </FieldContent>
              <Switch
                id="shell-enabled"
                checked={settings.shell_enabled}
                onCheckedChange={(checked) =>
                  void save(
                    { ...settings, shell_enabled: checked },
                    checked
                      ? "Assistant shell turned on"
                      : "Assistant shell turned off"
                  )
                }
              />
            </Field>
            <Field data-disabled={!settings.shell_enabled || undefined}>
              <FieldLabel htmlFor="shell-commands">Allowed programs</FieldLabel>
              <Textarea
                id="shell-commands"
                value={text}
                disabled={!settings.shell_enabled}
                onChange={(e) => setText(e.target.value)}
                onBlur={saveCommands}
                rows={6}
                spellCheck={false}
                // The shared Textarea grows with its content; a long allowlist
                // made the page scroll for a screen. Keep it at six lines.
                className="[field-sizing:fixed] max-h-48 font-mono"
              />
              <FieldDescription>
                One per line. Every program in a command is checked, including
                each part of a pipe (<code>|</code>) or chain (<code>&&</code>,{" "}
                <code>;</code>); others are refused before you&apos;re asked.
                This guards against mistakes, not a determined model: an allowed
                program can start others, so read each command before you
                approve it. Empty means no shell.
              </FieldDescription>
            </Field>
          </FieldGroup>
        )}
      </CardContent>
    </Card>
  )
}

/** One on/off setting: label, a single description, and the switch. */
function ToggleRow({
  id,
  label,
  checked,
  disabled,
  onChange,
  children,
}: {
  id: string
  label: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
  children: React.ReactNode
}) {
  return (
    <Field orientation="horizontal" data-disabled={disabled || undefined}>
      <FieldContent>
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        <FieldDescription>{children}</FieldDescription>
      </FieldContent>
      <Switch
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={onChange}
      />
    </Field>
  )
}

type ToggleKey =
  | "memory_enabled"
  | "web_research_enabled"
  | "docker_sandbox_enabled"
  | "durable_execution_enabled"
  | "coding_stack_enabled"
  | "browser_use_enabled"

function useToggle(settings: AiSettings | null, save: SaveAi) {
  return (key: ToggleKey, name: string) => (checked: boolean) => {
    if (!settings) return
    void save(
      { ...settings, [key]: checked },
      `${name} turned ${checked ? "on" : "off"}`
    )
  }
}

/** Everyday tools the assistant can use. Each is one switch. */
function ToolsCard({
  settings,
  save,
}: {
  settings: AiSettings | null
  save: SaveAi
}) {
  const toggle = useToggle(settings, save)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Memory and research</CardTitle>
        <CardDescription>
          What the assistant can keep between chats and look up on its own.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <FieldGroup>
            <ToggleRow
              id="memory-enabled"
              label="Remember across chats"
              checked={settings.memory_enabled}
              onChange={toggle("memory_enabled", "Memory")}
            >
              Keeps notes that later chats read, such as how this server is set
              up. Each admin has their own. Turning it off keeps the notes; the
              assistant just stops using them. Notes that look like hidden
              instructions are refused and written to the audit log.
            </ToggleRow>
            <ToggleRow
              id="web-research-enabled"
              label="Web research"
              checked={settings.web_research_enabled}
              onChange={toggle("web_research_enabled", "Web research")}
            >
              Searches the web with{" "}
              <a
                href="https://exa.ai"
                target="_blank"
                rel="noopener noreferrer"
              >
                Exa
              </a>{" "}
              and reads the pages it finds. The server needs an{" "}
              <code>EXA_API_KEY</code> environment variable before any search
              works.
            </ToggleRow>
            <FieldSeparator />
            <FieldDescription>
              Skills are instructions the assistant loads when a task needs
              them. Add one as a folder with a <code>SKILL.md</code> file in{" "}
              <code>assistant/skills</code> inside Athena&apos;s data folder.
            </FieldDescription>
          </FieldGroup>
        )}
      </CardContent>
    </Card>
  )
}

/** Opt-in features that need extra setup on the server. */
function AdvancedCard({
  settings,
  save,
}: {
  settings: AiSettings | null
  save: SaveAi
}) {
  const containers = useCapability("containers")
  const containersReady = containers?.status === "ready"
  const toggle = useToggle(settings, save)
  return (
    // The section heading above names it; a card title would repeat it.
    <Card>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <FieldGroup>
            <ToggleRow
              id="docker-sandbox-enabled"
              label="Docker sandbox"
              checked={settings.docker_sandbox_enabled}
              // Let an admin turn it off even when the engine went away.
              disabled={!containersReady && !settings.docker_sandbox_enabled}
              onChange={toggle("docker_sandbox_enabled", "Docker sandbox")}
            >
              Runs commands and edits files in an isolated container instead of
              on this server. Pulls a small Python image on first use.
              {!containersReady &&
                ` Needs ${containers?.label ?? "a container engine"} ready first.`}
            </ToggleRow>
            <ToggleRow
              id="coding-stack-enabled"
              label="Coding stack"
              checked={settings.coding_stack_enabled}
              onChange={toggle("coding_stack_enabled", "Coding stack")}
            >
              Reads <code>AGENTS.md</code> and <code>CLAUDE.md</code> from{" "}
              <code>assistant/code-workspace</code> in Athena&apos;s data
              folder, and reads or writes files there. Reading is free; every
              write shows an Approve/Deny card first.
            </ToggleRow>
            <ToggleRow
              id="durable-execution-enabled"
              label="Durable execution"
              checked={settings.durable_execution_enabled}
              onChange={toggle(
                "durable_execution_enabled",
                "Durable execution"
              )}
            >
              Checkpoints each model request and tool call, so an interrupted
              chat resumes instead of repeating paid work. Needs pgtask and a
              Postgres database (
              <code>ATHENA_DURABLE_EXECUTION_DATABASE_URL</code>
              ); without them it changes nothing.
            </ToggleRow>
            <ToggleRow
              id="browser-use-enabled"
              label="Browser agent"
              checked={settings.browser_use_enabled}
              // Nothing provides the browser tool yet (docs/STATUS.md → Next),
              // so it can only be turned off.
              disabled={!settings.browser_use_enabled}
              onChange={toggle("browser_use_enabled", "Browser agent")}
            >
              Hands open-ended web tasks to an autonomous browser. Not available
              yet: it waits for a browser-use release that installs alongside
              the rest of the server.
            </ToggleRow>
          </FieldGroup>
        )}
      </CardContent>
    </Card>
  )
}

function ReviewCard({
  settings,
  save,
}: {
  settings: AiSettings | null
  save: SaveAi
}) {
  const { providers } = useModels()

  function saveModel(ref: ModelRef | null) {
    if (!settings || ref === settings.review_model) return
    void save(
      {
        ...settings,
        review_model: ref,
        // No model means nothing can review; keep the two in step.
        review_tool_calls: ref ? settings.review_tool_calls : false,
      },
      ref ? "Review model saved" : "Review turned off"
    )
  }

  // Nothing to pick from until a provider exists; Providers above says so.
  if (!providers?.length && settings !== null) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review tool calls</CardTitle>
        <CardDescription>
          A second model checks each action before it reaches your Approve/Deny
          card and approves the clearly safe ones, so you only see the risky
          ones.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="review-model">Review model</FieldLabel>
              <div className="flex gap-2">
                <ModelPicker
                  id="review-model"
                  variant="field"
                  className="flex-1"
                  providers={providers}
                  value={settings.review_model}
                  onChange={saveModel}
                />
                {settings.review_model && (
                  <Button variant="outline" onClick={() => saveModel(null)}>
                    Clear
                  </Button>
                )}
              </div>
              <FieldDescription>
                Its provider sees each call&apos;s name and arguments, not the
                whole chat. Every check is one more model call and counts toward
                the spend limit.
              </FieldDescription>
            </Field>
            <ToggleRow
              id="review-tool-calls"
              label="Review before asking me"
              checked={settings.review_tool_calls}
              disabled={!settings.review_model && !settings.review_tool_calls}
              onChange={(checked) =>
                void save(
                  { ...settings, review_tool_calls: checked },
                  checked
                    ? "Tool-call reviewing turned on"
                    : "Tool-call reviewing turned off"
                )
              }
            >
              {settings.review_model
                ? "Safe actions are approved for you; risky ones still reach your card."
                : "Pick a review model first."}
            </ToggleRow>
          </FieldGroup>
        )}
      </CardContent>
    </Card>
  )
}

function IntegrationsCard({
  settings,
  save,
}: {
  settings: AiSettings | null
  save: SaveAi
}) {
  const [kinds, setKinds] = React.useState<IntegrationKind[]>([])
  const [integrations, setIntegrations] = React.useState<Integration[] | null>(
    null
  )
  const [editing, setEditing] = React.useState<{
    integration: Integration | null
    kinds: IntegrationKind[]
  } | null>(null)
  const [removing, setRemoving] = React.useState<Integration | null>(null)
  const [version, setVersion] = React.useState(0)

  React.useEffect(() => {
    void (async () => {
      const [k, i] = await Promise.all([
        api.GET("/api/assistant/integrations/kinds"),
        api.GET("/api/assistant/integrations"),
      ])
      setKinds(k.data ?? [])
      setIntegrations(i.data ?? [])
    })()
  }, [])

  async function remove(integration: Integration) {
    setRemoving(null)
    const { error } = await api.DELETE(
      "/api/assistant/integrations/{integration_id}",
      {
        params: { path: { integration_id: integration.id } },
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
    setVersion((v) => v + 1)
  }

  function saved(integration: Integration) {
    setEditing(null)
    setVersion((v) => v + 1)
  }

  const list = integrations ?? []
  const transportSummary = (t: Integration["transport"]) =>
    t.type === "stdio"
      ? `${t.command} ${(t.args ?? []).join(" ")}`.trim()
      : (t as { url: string }).url

  if (integrations === null) {
    return <Skeleton className="h-24 w-full" />
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hosted integrations</CardTitle>
        <CardDescription>
          MCP servers Athena runs for the assistant (GitHub, Linear, Notion, …).
          Each has an encrypted token, and its actions go through your
          Approve/Deny card.
        </CardDescription>
        <CardAction>
          {kinds.length ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditing({ integration: null, kinds })}
            >
              <PlusIcon />
              Add integration
            </Button>
          ) : null}
        </CardAction>
      </CardHeader>
      <CardContent>
        {list.length === 0 ? (
          <Empty className="border">
            <EmptyHeader>
              <EmptyTitle>No integrations yet</EmptyTitle>
            </EmptyHeader>
          </Empty>
        ) : (
          <ItemGroup className="gap-2">
            {list.map((integration) => (
              <Item key={integration.id} variant="outline" size="sm">
                <ItemContent>
                  <ItemTitle>{integration.name}</ItemTitle>
                  <ItemDescription>
                    {kinds.find((k) => k.id === integration.kind)?.label ??
                      integration.kind}
                    {` · ${transportSummary(integration.transport)}`}
                    {integration.secrets_set?.length ? " · token set" : ""}
                  </ItemDescription>
                </ItemContent>
                <ItemActions>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Edit ${integration.name}`}
                    onClick={() => setEditing({ integration, kinds })}
                  >
                    <PencilIcon />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Remove ${integration.name}`}
                    onClick={() => setRemoving(integration)}
                  >
                    <Trash2Icon />
                  </Button>
                </ItemActions>
              </Item>
            ))}
          </ItemGroup>
        )}
      </CardContent>
      <IntegrationDialog
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
              Its token is deleted from this server. Chats that used its tools
              will no longer have them.
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

const SECTIONS = [
  { id: "models", title: "Models" },
  { id: "tools", title: "Tools" },
  { id: "advanced", title: "Advanced" },
] as const

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex scroll-mt-20 flex-col gap-4"
    >
      <div className="flex flex-col gap-1">
        <h2 id={`${id}-title`} className="font-heading text-base font-medium">
          {title}
        </h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  )
}

/** Settings → AI: providers, default models, tools and limits (admins only). */
export function AiSettingsView() {
  const { user } = useAuth()
  const [version, setVersion] = React.useState(0)
  const { settings, save } = useAiSettings(version)
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
    <div className="flex flex-col gap-8">
      <nav aria-label="AI settings sections" className="flex flex-wrap gap-1">
        {SECTIONS.map((s) => (
          <Button
            key={s.id}
            variant="outline"
            size="sm"
            nativeButton={false}
            render={<a href={`#${s.id}`} />}
          >
            {s.title}
          </Button>
        ))}
      </nav>
      <Section
        id="models"
        title="Models"
        description="Where the assistant's models come from and which ones it uses."
      >
        <ProvidersCard onChanged={() => setVersion((v) => v + 1)} />
        <DefaultsCard version={version} settings={settings} save={save} />
        <ReviewCard settings={settings} save={save} />
      </Section>
      <Section
        id="tools"
        title="Tools"
        description="What the assistant can do besides managing apps, packages and files."
      >
        <ToolsCard settings={settings} save={save} />
        <IntegrationsCard settings={settings} save={save} />
        <ShellCard settings={settings} save={save} />
      </Section>
      <Section
        id="advanced"
        title="Advanced"
        description="Off by default. Each one needs something extra on the server."
      >
        <AdvancedCard settings={settings} save={save} />
      </Section>
    </div>
  )
}
