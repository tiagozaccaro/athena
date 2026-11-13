"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { ChevronDownIcon, DownloadIcon } from "lucide-react"

import { api, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@workspace/ui/components/collapsible"
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
import { Spinner } from "@workspace/ui/components/spinner"
import { Switch } from "@workspace/ui/components/switch"

import { useAppJobs } from "@/components/apps/use-app-jobs"

type Detail = Schemas["StoreAppDetail"]
type FormField = Schemas["FormField"]

const NAME_RE = /^[a-z0-9][a-z0-9_-]{0,62}$/

function FieldControl({
  field,
  value,
  invalid,
  onChange,
}: {
  field: FormField
  value: string
  invalid: boolean
  onChange: (value: string) => void
}) {
  const id = `field-${field.key}`
  if (field.type === "boolean") {
    return (
      <Switch
        id={id}
        checked={value === "true"}
        onCheckedChange={(checked) => onChange(checked ? "true" : "false")}
      />
    )
  }
  if (field.type === "select") {
    const items = (field.options ?? []).map((o) => ({ label: o, value: o }))
    return (
      <Select
        items={items}
        value={value}
        onValueChange={(v) => onChange((v as string) ?? "")}
      >
        <SelectTrigger id={id} aria-invalid={invalid || undefined}>
          <SelectValue />
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
    )
  }
  return (
    <Input
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      type={
        field.type === "password"
          ? "password"
          : field.type === "port" || field.type === "number"
            ? "number"
            : "text"
      }
      inputMode={field.type === "port" ? "numeric" : undefined}
      placeholder={field.generated ? "Generated if left empty" : undefined}
      autoComplete={field.type === "password" ? "new-password" : "off"}
      className={field.type === "path" ? "font-mono text-xs" : undefined}
      aria-invalid={invalid || undefined}
    />
  )
}

export function InstallForm({ app }: { app: Detail }) {
  const router = useRouter()
  const [name, setName] = React.useState(app.suggested_name)
  const [values, setValues] = React.useState<Record<string, string>>(() =>
    Object.fromEntries(app.fields.map((f) => [f.key, f.default]))
  )
  const [errors, setErrors] = React.useState<Record<string, string>>({})
  const [installing, setInstalling] = React.useState(false)
  const installedName = React.useRef(name)

  const jobs = useAppJobs((ok) => {
    if (ok)
      router.push(
        `/apps/view/?name=${encodeURIComponent(installedName.current)}`
      )
  })

  const nameError =
    name && !NAME_RE.test(name)
      ? "Use lowercase letters, digits, dashes or underscores."
      : (errors.__name ?? null)

  async function install(event: React.FormEvent) {
    event.preventDefault()
    setInstalling(true)
    setErrors({})
    installedName.current = name
    const result = await api.POST(
      "/api/store/apps/{catalog}/{app_id}/install",
      {
        params: { path: { catalog: app.catalog, app_id: app.id } },
        body: { name, values },
      }
    )
    setInstalling(false)
    const detail = (result.error as { detail?: unknown } | undefined)?.detail
    if (detail && typeof detail === "object" && "errors" in detail) {
      setErrors((detail as { errors: Record<string, string> }).errors)
      return
    }
    if (typeof detail === "string" && detail.includes("exists")) {
      setErrors({ __name: detail })
      return
    }
    jobs.show(result, `install ${app.title}`)
  }

  const basic = app.fields.filter((f) => !f.advanced)
  const advanced = app.fields.filter((f) => f.advanced)

  const renderField = (f: FormField) => (
    <Field
      key={f.key}
      orientation={f.type === "boolean" ? "horizontal" : undefined}
      data-invalid={errors[f.key] ? true : undefined}
    >
      <FieldLabel htmlFor={`field-${f.key}`}>{f.label}</FieldLabel>
      <FieldControl
        field={f}
        value={values[f.key] ?? ""}
        invalid={Boolean(errors[f.key])}
        onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))}
      />
      {errors[f.key] ? (
        <FieldError>{errors[f.key]}</FieldError>
      ) : f.description ? (
        <FieldDescription>{f.description}</FieldDescription>
      ) : null}
    </Field>
  )

  return (
    <form onSubmit={install} className="flex flex-col gap-6">
      <FieldGroup>
        <Field data-invalid={nameError ? true : undefined}>
          <FieldLabel htmlFor="install-name">App name</FieldLabel>
          <Input
            id="install-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={nameError ? true : undefined}
            autoComplete="off"
          />
          {nameError ? (
            <FieldError>{nameError}</FieldError>
          ) : (
            <FieldDescription>
              Install the same app twice under different names if you need to.
            </FieldDescription>
          )}
        </Field>
        {basic.map(renderField)}
      </FieldGroup>

      {advanced.length > 0 ? (
        <Collapsible>
          <CollapsibleTrigger
            render={
              <Button variant="ghost" size="sm" className="group/adv -ml-2" />
            }
          >
            Advanced settings
            <ChevronDownIcon
              data-icon="inline-end"
              className="transition-transform group-data-panel-open/adv:rotate-180"
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <FieldGroup className="pt-4">
              {advanced.map(renderField)}
            </FieldGroup>
          </CollapsibleContent>
        </Collapsible>
      ) : null}

      <div>
        <Button type="submit" disabled={!name || !!nameError || installing}>
          {installing ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <DownloadIcon data-icon="inline-start" />
          )}
          Install {app.title}
        </Button>
      </div>
      {jobs.dialog}
    </form>
  )
}
