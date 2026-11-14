"use client"

import * as React from "react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@workspace/ui/components/combobox"
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
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import { Switch } from "@workspace/ui/components/switch"
import { Textarea } from "@workspace/ui/components/textarea"
import { toast } from "@workspace/ui/components/toast"

type Provider = Schemas["Provider"]
type Option = Schemas["ProviderOption"]
type Question = Schemas["ConfigQuestion"]
type Step = Schemas["ConfigStep"]

/** `null` closes the dialog; `{name: null}` adds a remote. */
export type RemoteEditing = { name: string | null } | null

/** For backends with sub-providers (S3): does `option` apply to this one? */
function appliesTo(option: Option, provider: string | undefined): boolean {
  if (!option.provider) return true
  const list = option.provider.replace(/^!/, "").split(",")
  const listed = provider !== undefined && list.includes(provider)
  return option.provider.startsWith("!") ? !listed : listed
}

/** rclone's help starts with a short summary line, then details after a blank line. */
function firstParagraph(help: string): string {
  return help.split("\n\n")[0]!.trim()
}

const ACRONYMS = new Set(["id", "url", "api", "sse", "kms", "acl", "uri", "ssl", "tls"])

/** "client_id" → "Client ID": rclone names options for config files, not people. */
export function optionLabel(name: string): string {
  const words = name.split("_").map((w) => (ACRONYMS.has(w) ? w.toUpperCase() : w))
  const first = words[0] ?? ""
  words[0] = first.charAt(0).toUpperCase() + first.slice(1)
  return words.join(" ")
}

/** One rclone setting as a form field: a choice, a yes/no, a password or text. */
function OptionField({
  option,
  value,
  onChange,
  secretSet,
  error,
}: {
  option: Option
  value: string
  onChange: (value: string) => void
  /** Editing, and a value is stored but not shown. */
  secretSet?: boolean
  error?: string
}) {
  const id = `opt-${option.name}`
  const examples = option.examples ?? []
  const label = (
    <FieldLabel htmlFor={id} title={option.name}>
      {optionLabel(option.name)}
      {option.required ? null : (
        <span className="font-normal text-muted-foreground">(optional)</span>
      )}
    </FieldLabel>
  )
  const description = option.help ? (
    <FieldDescription className="whitespace-pre-line">
      {firstParagraph(option.help)}
    </FieldDescription>
  ) : null

  if (option.type === "bool" && !examples.length) {
    const on = (value || option.default) === "true"
    return (
      <Field orientation="horizontal" data-invalid={error ? true : undefined}>
        <Switch
          id={id}
          checked={on}
          onCheckedChange={(c) => onChange(c ? "true" : "false")}
        />
        <div className="flex flex-col gap-1">
          {label}
          {description}
          {error ? <FieldError>{error}</FieldError> : null}
        </div>
      </Field>
    )
  }

  if (examples.length && (option.exclusive || option.type === "bool")) {
    const items = examples.map((e) => ({
      value: e.value,
      label: e.help ? `${e.help.split("\n")[0]} (${e.value})` : e.value,
    }))
    return (
      <Field data-invalid={error ? true : undefined}>
        {label}
        <Select
          items={items}
          value={value || option.default || null}
          onValueChange={(v) => onChange(v ?? "")}
        >
          <SelectTrigger id={id} className="w-full">
            <SelectValue placeholder="Choose…" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {items.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        {description}
        {error ? <FieldError>{error}</FieldError> : null}
      </Field>
    )
  }

  const listId = examples.length ? `${id}-examples` : undefined
  return (
    <Field data-invalid={error ? true : undefined}>
      {label}
      <Input
        id={id}
        type={option.password ? "password" : "text"}
        autoComplete={option.password ? "new-password" : "off"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={
          secretSet ? "Unchanged" : option.default ? option.default : undefined
        }
        list={listId}
        aria-invalid={error ? true : undefined}
      />
      {listId ? (
        <datalist id={listId}>
          {examples.map((e) => (
            <option key={e.value} value={e.value}>
              {e.help.split("\n")[0]}
            </option>
          ))}
        </datalist>
      ) : null}
      {description}
      {error ? <FieldError>{error}</FieldError> : null}
    </Field>
  )
}

/** One of rclone's follow-up questions (OAuth token, which drive, ...). */
function QuestionForm({
  question,
  refused,
  onAnswer,
  onCancel,
}: {
  question: Question
  /** Why rclone refused the last answer to this question. */
  refused: string
  onAnswer: (answer: string) => Promise<void>
  onCancel: () => void
}) {
  const option = question.option
  const [value, setValue] = React.useState("")
  const [pending, setPending] = React.useState(false)
  React.useEffect(() => setValue(""), [question.state])
  const yesNo = option.type === "bool"
  const long = option.name === "config_token" || option.help.includes("paste")

  async function send(answer: string) {
    setPending(true)
    await onAnswer(answer)
    setPending(false)
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        void send(value || option.default)
      }}
    >
      <p className="rounded-lg border bg-muted/50 p-3 text-sm whitespace-pre-wrap">
        {option.help.trim()}
      </p>
      {refused || question.error ? (
        <FieldError className="whitespace-pre-wrap">
          {refused || question.error}
        </FieldError>
      ) : null}
      {yesNo ? null : option.examples?.length && option.exclusive ? (
        <OptionField option={option} value={value} onChange={setValue} />
      ) : long ? (
        <Field>
          <FieldLabel htmlFor="answer">Paste the result</FieldLabel>
          <Textarea
            id="answer"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="min-h-28 font-mono text-xs"
            required={option.required}
          />
        </Field>
      ) : (
        <OptionField option={option} value={value} onChange={setValue} />
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        {yesNo ? (
          <>
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={() => void send("false")}
            >
              No
            </Button>
            <Button
              type="button"
              disabled={pending}
              onClick={() => void send("true")}
            >
              {pending ? <Spinner data-icon="inline-start" /> : null}
              Yes
            </Button>
          </>
        ) : (
          <Button type="submit" disabled={pending}>
            {pending ? <Spinner data-icon="inline-start" /> : null}
            Continue
          </Button>
        )}
      </DialogFooter>
    </form>
  )
}

/**
 * Add or edit a cloud remote. The form comes from rclone's description of the
 * storage type; rclone may then ask follow-up questions, answered one at a time.
 */
export function RemoteDialog({
  editing,
  onClose,
  onSaved,
}: {
  editing: RemoteEditing
  onClose: () => void
  onSaved: () => void
}) {
  const [providers, setProviders] = React.useState<Provider[] | null>(null)
  const [detail, setDetail] = React.useState<Schemas["RemoteDetail"] | null>(
    null
  )
  const [name, setName] = React.useState("")
  const [type, setType] = React.useState<string | null>(null)
  const [values, setValues] = React.useState<Record<string, string>>({})
  const [advanced, setAdvanced] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [pending, setPending] = React.useState(false)
  const [step, setStep] = React.useState<Step | null>(null)
  const [refused, setRefused] = React.useState("")
  const isNew = editing?.name === null

  React.useEffect(() => {
    if (!editing) return
    setError(null)
    setStep(null)
    setRefused("")
    setAdvanced(false)
    setDetail(null)
    setName(editing.name ?? "")
    setType(null)
    setValues({})
    void api.GET("/api/cloud/providers").then(({ data, error }) => {
      if (data) setProviders(data)
      else setError(errorMessage(error))
    })
    if (editing.name !== null) {
      void api
        .GET("/api/cloud/remotes/{name}", {
          params: { path: { name: editing.name } },
        })
        .then(({ data, error }) => {
          if (!data) {
            setError(errorMessage(error))
            return
          }
          setDetail(data)
          setType(data.type)
          setValues(data.values)
        })
    }
  }, [editing])

  const provider = providers?.find((p) => p.name === type)
  const subProvider = values.provider
  const options = (provider?.options ?? []).filter((o) =>
    appliesTo(o, subProvider)
  )
  const basic = options.filter((o) => !o.advanced)
  const extra = options.filter((o) => o.advanced)
  const secrets = new Set(detail?.secrets ?? [])
  const remoteName = isNew ? name.trim() : (editing?.name ?? "")

  async function handle(result: {
    data?: Step
    error?: unknown
  }): Promise<void> {
    if (!result.data) {
      setError(errorMessage(result.error))
      return
    }
    setError(null)
    setRefused(result.data.error ?? "")
    if (!result.data.done && !result.data.question) {
      // Refused: keep asking the same question.
      if (!step) setError(result.data.error || "rclone refused that")
      return
    }
    if (result.data.done) {
      toast.add({
        type: "success",
        title: isNew ? `Added ${result.data.remote}` : `Saved ${result.data.remote}`,
      })
      setStep(null)
      onSaved()
      onClose()
    } else setStep(result.data)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!type) return
    setPending(true)
    // Only send what was filled in or changed; rclone keeps its defaults.
    const parameters = Object.fromEntries(
      Object.entries(values).filter(
        ([k, v]) => v !== (detail?.values[k] ?? "") || (isNew && v !== "")
      )
    )
    const result = isNew
      ? await api.POST("/api/cloud/remotes", {
          body: { name: remoteName, type, parameters },
        })
      : await api.PUT("/api/cloud/remotes/{name}", {
          params: { path: { name: remoteName } },
          body: { parameters },
        })
    setPending(false)
    if (isNew && result.data) onSaved()
    await handle(result)
  }

  async function answer(value: string) {
    if (!step?.question) return
    await handle(
      await api.POST("/api/cloud/remotes/{name}/answer", {
        params: { path: { name: step.remote } },
        body: { state: step.question.state, answer: value },
      })
    )
  }

  async function cancel() {
    // A new remote that stopped halfway isn't usable: forget it.
    if (isNew && step) {
      await api.DELETE("/api/cloud/remotes/{name}", {
        params: { path: { name: step.remote } },
      })
      onSaved()
    }
    onClose()
  }

  const providerItems = providers ?? []

  return (
    <Dialog
      open={editing !== null}
      onOpenChange={(open) => !open && void cancel()}
    >
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {isNew ? "Add a remote" : `Edit ${editing?.name ?? ""}`}
          </DialogTitle>
          <DialogDescription>
            {step
              ? "rclone needs one more answer to finish setting it up."
              : provider
                ? provider.description
                : "Cloud storage that rclone connects to: Google Drive, OneDrive, Dropbox, S3, WebDAV and many more."}
          </DialogDescription>
        </DialogHeader>
        {step?.question ? (
          <QuestionForm
            question={step.question}
            refused={refused}
            onAnswer={answer}
            onCancel={() => void cancel()}
          />
        ) : providers === null || (!isNew && detail === null) ? (
          error ? (
            <FieldError>{error}</FieldError>
          ) : (
            <Skeleton className="h-48 w-full" />
          )
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <FieldGroup>
              {isNew ? (
                <>
                  <Field>
                    <FieldLabel htmlFor="remote-name">Name</FieldLabel>
                    <Input
                      id="remote-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="gdrive"
                      required
                      autoComplete="off"
                    />
                    <FieldDescription>
                      How it shows in Files, e.g. gdrive or backups.
                    </FieldDescription>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="remote-type">Storage</FieldLabel>
                    <Combobox
                      items={providerItems}
                      value={provider ?? null}
                      onValueChange={(p: Provider | null) => {
                        setType(p?.name ?? null)
                        setValues({})
                      }}
                      itemToStringLabel={(p: Provider) => p.description}
                      itemToStringValue={(p: Provider) => p.name}
                    >
                      <ComboboxInput
                        id="remote-type"
                        placeholder="Search: Drive, S3, Dropbox…"
                        className="w-full"
                      />
                      <ComboboxContent>
                        <ComboboxEmpty>No storage type matches.</ComboboxEmpty>
                        <ComboboxList>
                          {(p: Provider) => (
                            <ComboboxItem key={p.name} value={p}>
                              <span className="truncate">{p.description}</span>
                              <span className="ml-auto font-mono text-xs text-muted-foreground">
                                {p.name}
                              </span>
                            </ComboboxItem>
                          )}
                        </ComboboxList>
                      </ComboboxContent>
                    </Combobox>
                  </Field>
                </>
              ) : null}
              {basic.map((option) => (
                <OptionField
                  key={option.name}
                  option={option}
                  value={values[option.name] ?? ""}
                  secretSet={secrets.has(option.name)}
                  onChange={(v) => setValues((s) => ({ ...s, [option.name]: v }))}
                />
              ))}
              {extra.length ? (
                <Field orientation="horizontal">
                  <Switch
                    id="show-advanced"
                    checked={advanced}
                    onCheckedChange={setAdvanced}
                  />
                  <FieldLabel htmlFor="show-advanced">
                    Advanced settings ({extra.length})
                  </FieldLabel>
                </Field>
              ) : null}
              {advanced
                ? extra.map((option) => (
                    <OptionField
                      key={option.name}
                      option={option}
                      value={values[option.name] ?? ""}
                      secretSet={secrets.has(option.name)}
                      onChange={(v) =>
                        setValues((s) => ({ ...s, [option.name]: v }))
                      }
                    />
                  ))
                : null}
              {error ? <FieldError>{error}</FieldError> : null}
            </FieldGroup>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={pending || !type || !remoteName}>
                {pending ? <Spinner data-icon="inline-start" /> : null}
                {isNew ? "Add" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
