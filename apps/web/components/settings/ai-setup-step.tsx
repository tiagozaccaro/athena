"use client"

import * as React from "react"
import { CheckCircle2Icon, CpuIcon, TriangleAlertIcon } from "lucide-react"

import { api, errorMessage } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
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
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"

import { ModelPicker } from "@/components/assistant/model-picker"
import { useModels, type ModelRef } from "@/components/assistant/use-models"
import {
  ProviderDialog,
  type Provider,
  type ProviderEditing,
  type ProviderKind,
} from "@/components/settings/ai-provider-dialog"
import { AddMenu } from "@/components/settings/ai-settings"
import {
  editingFor,
  LocalServerButtons,
  localServersSentence,
  useLocalAiServers,
} from "@/components/settings/local-ai-servers"

type Test = { ok: boolean; message: string } | "testing" | null

/**
 * The setup wizard's optional AI step (docs/design/assistant.md): add a first
 * provider (one click for a detected Ollama), check it connects, and pick the
 * default model. Everything here is also in Settings → AI.
 * Needs a `CapabilitiesProvider` and a signed-in admin.
 */
export function AiSetupStep({ onDone }: { onDone: () => void }) {
  const [kinds, setKinds] = React.useState<ProviderKind[]>([])
  const [editing, setEditing] = React.useState<ProviderEditing>(null)
  const [provider, setProvider] = React.useState<Provider | null>(null)
  const [test, setTest] = React.useState<Test>(null)
  const [model, setModel] = React.useState<ModelRef | null>(null)
  const [saveError, setSaveError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)
  const { providers: models, reload } = useModels()

  React.useEffect(() => {
    void api
      .GET("/api/assistant/kinds")
      .then(({ data }) => setKinds(data ?? []))
  }, [])

  const local = useLocalAiServers(kinds)
  const kindOf = (id: string) => kinds.find((k) => k.id === id)

  async function check(p: Provider) {
    setTest("testing")
    const { data, error } = await api.POST(
      "/api/assistant/providers/{provider_id}/test",
      { params: { path: { provider_id: p.id } } }
    )
    setTest(
      data ?? { ok: false, message: errorMessage(error, "Couldn't connect") }
    )
    await reload()
  }

  function saved(p: Provider) {
    setEditing(null)
    setProvider(p)
    setModel(null)
    void check(p)
  }

  async function finish() {
    if (!model) return onDone()
    setSaving(true)
    setSaveError(null)
    // PUT replaces the whole row, so start from what's stored.
    const current = await api.GET("/api/settings/ai")
    const { data, error } = current.data
      ? await api.PUT("/api/settings/ai", {
          body: { ...current.data, default_model: model },
        })
      : current
    setSaving(false)
    if (!data) {
      setSaveError(errorMessage(error, "Couldn't save the default model"))
      return
    }
    onDone()
  }

  const providerModels = provider
    ? (models ?? []).filter((m) => m.provider_id === provider.id)
    : []

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">Set up the AI assistant</CardTitle>
        <CardDescription>
          Optional. The assistant answers questions about this server and, with
          your approval, installs apps and manages packages and files.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!provider ? (
          <div className="flex flex-col gap-3">
            {local.length ? (
              <>
                <p className="text-sm text-muted-foreground">
                  {localServersSentence(local)}
                </p>
                <LocalServerButtons
                  servers={local}
                  onUse={(server) => setEditing(editingFor(server))}
                />
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Add a cloud provider with an API key, or a local one such as
                Ollama, LM Studio or llama.cpp.
              </p>
            )}
            <AddMenu
              kinds={kinds}
              onPick={(kind) => setEditing({ kind })}
              label={local.length ? "Another provider" : "Add a provider"}
            />
          </div>
        ) : (
          <FieldGroup>
            {test === "testing" || test === null ? (
              <Alert>
                <Spinner />
                <AlertTitle>Connecting to {provider.name}…</AlertTitle>
              </Alert>
            ) : test.ok ? (
              <Alert>
                <CheckCircle2Icon />
                <AlertTitle>{provider.name} is connected</AlertTitle>
                <AlertDescription>{test.message}</AlertDescription>
              </Alert>
            ) : (
              <Alert variant="destructive">
                <TriangleAlertIcon />
                <AlertTitle>{provider.name} didn&apos;t connect</AlertTitle>
                <AlertDescription>
                  <p>{test.message}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => {
                      const kind = kindOf(provider.kind)
                      if (kind) setEditing({ kind, provider })
                    }}
                  >
                    Edit provider
                  </Button>
                </AlertDescription>
              </Alert>
            )}
            <Field data-invalid={saveError ? true : undefined}>
              <FieldLabel htmlFor="setup-default-model">
                Default model
              </FieldLabel>
              {models === null || test === "testing" ? (
                <Skeleton className="h-9 w-full" />
              ) : (
                <ModelPicker
                  id="setup-default-model"
                  variant="field"
                  providers={providerModels}
                  value={model}
                  onChange={setModel}
                />
              )}
              <FieldDescription>
                New chats start with it. Only models that can use tools work
                with the assistant.
              </FieldDescription>
              {saveError ? <FieldError>{saveError}</FieldError> : null}
            </Field>
          </FieldGroup>
        )}
      </CardContent>
      <CardFooter className="flex-col gap-2">
        {provider ? (
          <Button
            className="w-full"
            disabled={saving || test === "testing"}
            onClick={() => void finish()}
          >
            {saving ? <Spinner /> : null}
            Finish
          </Button>
        ) : null}
        <Button
          variant="ghost"
          className="w-full"
          disabled={saving}
          onClick={onDone}
        >
          {provider ? "Skip the default model" : "Skip for now"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          You can change this later in Settings → AI.
        </p>
      </CardFooter>
      <ProviderDialog
        editing={editing}
        onClose={() => setEditing(null)}
        onSaved={saved}
      />
    </Card>
  )
}
