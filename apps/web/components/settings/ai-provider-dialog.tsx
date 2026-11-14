"use client"

import * as React from "react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Spinner } from "@workspace/ui/components/spinner"

export type ProviderKind = Schemas["ProviderKind"]
export type Provider = Schemas["ProviderOut"]

/** `kind` adds a provider of that kind; `provider` edits one. */
export type ProviderEditing =
  | {
      kind: ProviderKind
      provider?: undefined
      values?: Record<string, string>
    }
  | { kind: ProviderKind; provider: Provider; values?: undefined }
  | null

/** Add or edit an AI provider. Saved keys are never shown; empty keeps them. */
export function ProviderDialog({
  editing,
  onClose,
  onSaved,
}: {
  editing: ProviderEditing
  onClose: () => void
  onSaved: (provider: Provider) => void
}) {
  const kind = editing?.kind
  const existing = editing?.provider
  const [name, setName] = React.useState("")
  const [values, setValues] = React.useState<Record<string, string>>({})
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    if (!editing) return
    setName(editing.provider?.name ?? editing.kind.label)
    setValues({
      ...(editing.provider?.values ?? {}),
      ...(editing.values ?? {}),
    })
    setError(null)
  }, [editing])

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!kind) return
    setSaving(true)
    setError(null)
    const result = existing
      ? await api.PUT("/api/assistant/providers/{provider_id}", {
          params: { path: { provider_id: existing.id } },
          body: { name, values },
        })
      : await api.POST("/api/assistant/providers", {
          body: { kind: kind.id, name, values },
        })
    setSaving(false)
    if (result.data) onSaved(result.data)
    else setError(errorMessage(result.error))
  }

  return (
    <Dialog open={editing !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-lg">
        <form onSubmit={save} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>
              {existing
                ? `Edit ${existing.name}`
                : `Add ${kind?.label ?? "provider"}`}
            </DialogTitle>
            <DialogDescription>
              Keys are stored encrypted on this server and never sent back to
              the browser.
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="provider-name">Name</FieldLabel>
              <Input
                id="provider-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={64}
                required
              />
              <FieldDescription>
                Shown in the model picker, e.g. “Work key”.
              </FieldDescription>
            </Field>
            {kind?.fields.map((f) => {
              const id = `provider-${f.key}`
              const stored = existing?.secrets_set.includes(f.key) ?? false
              return (
                <Field key={f.key}>
                  <FieldLabel htmlFor={id}>
                    {f.label}
                    {f.required ? null : (
                      <span className="font-normal text-muted-foreground">
                        (optional)
                      </span>
                    )}
                  </FieldLabel>
                  <Input
                    id={id}
                    type={f.secret ? "password" : "text"}
                    autoComplete={f.secret ? "new-password" : "off"}
                    value={values[f.key] ?? ""}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [f.key]: e.target.value }))
                    }
                    placeholder={
                      stored
                        ? "Unchanged"
                        : (f.placeholder ?? f.default ?? undefined)
                    }
                    required={f.required && !stored && !f.default}
                  />
                  {f.help ? (
                    <FieldDescription>{f.help}</FieldDescription>
                  ) : null}
                </Field>
              )
            })}
            {error ? <FieldError>{error}</FieldError> : null}
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Spinner /> : null}
              {existing ? "Save" : "Add"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
