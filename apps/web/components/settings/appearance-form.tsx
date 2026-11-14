"use client"

import * as React from "react"
import {
  CheckIcon,
  CopyIcon,
  MonitorIcon,
  MoonIcon,
  SunIcon,
} from "lucide-react"

import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
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
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { toast } from "@workspace/ui/components/toast"
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@workspace/ui/components/toggle-group"

import { useAppearance } from "@/components/settings/appearance-provider"
import {
  type Appearance,
  BASES,
  CHARTS,
  FONTS,
  fromPresetCode,
  label,
  RADII,
  THEMES,
  toPresetCode,
  withBase,
} from "@/lib/appearance"

type Option = { id: string; label: string; swatch?: string }

/** A single-choice row of swatch toggles. Clicking the selected one keeps it selected. */
function SwatchPicker({
  id,
  options,
  value,
  onChange,
}: {
  id: string
  options: Option[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <ToggleGroup
      aria-labelledby={id}
      value={[value]}
      onValueChange={(v: string[]) => v[0] && onChange(v[0])}
      variant="outline"
      size="sm"
      spacing={2}
      className="flex-wrap"
    >
      {options.map((o) => (
        <ToggleGroupItem key={o.id} value={o.id} aria-label={o.label}>
          {o.swatch ? (
            <span
              aria-hidden
              className="size-3.5 shrink-0 rounded-full border border-border"
              style={{ background: o.swatch }}
            />
          ) : null}
          {o.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

function FontSelect({
  id,
  value,
  onChange,
  inherit,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  inherit?: boolean
}) {
  const items = [
    ...(inherit ? [{ value: "inherit", label: "Same as body" }] : []),
    ...FONTS.map((f) => ({ value: f, label: label(f) })),
  ]
  return (
    <Select
      items={items}
      value={value}
      onValueChange={(v) => v && onChange(v as string)}
    >
      <SelectTrigger id={id} className="w-full sm:w-72">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {items.map((item) => (
            <SelectItem
              key={item.value}
              value={item.value}
              // Each option is shown in its own font (fetched the first time it's seen).
              style={
                item.value === "inherit"
                  ? undefined
                  : { fontFamily: `var(--font-${item.value})` }
              }
            >
              {item.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

function PresetCode({
  appearance,
  update,
}: {
  appearance: Appearance
  update: (next: Appearance) => void
}) {
  const code = toPresetCode(appearance)
  const [input, setInput] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [copied, setCopied] = React.useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.add({ type: "error", title: "Couldn't copy to the clipboard" })
    }
  }

  function apply(event: React.FormEvent) {
    event.preventDefault()
    const result = fromPresetCode(input, appearance)
    if (!result) {
      setError("That isn't a shadcn preset code.")
      return
    }
    setError(null)
    setInput("")
    update(result.appearance)
    toast.add({
      type: result.ignored.length ? "warning" : "success",
      title: `Applied preset ${input.trim()}`,
      description: result.ignored.length
        ? `Athena can't apply ${result.ignored.join(", ")} yet, so those parts were skipped.`
        : undefined,
    })
  }

  return (
    <FieldGroup>
      <Field>
        <FieldLabel htmlFor="preset-current">Current preset code</FieldLabel>
        <div className="flex gap-2">
          <Input
            id="preset-current"
            value={code}
            readOnly
            className="font-mono sm:w-56"
          />
          <Button type="button" variant="outline" onClick={copy}>
            {copied ? (
              <CheckIcon data-icon="inline-start" />
            ) : (
              <CopyIcon data-icon="inline-start" />
            )}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <FieldDescription>
          Use it with <code>npx shadcn init --preset {code}</code>, or share it.
        </FieldDescription>
      </Field>
      <form onSubmit={apply}>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="preset-import">Apply a preset code</FieldLabel>
          <div className="flex gap-2">
            <Input
              id="preset-import"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="b0"
              className="font-mono sm:w-56"
              aria-invalid={error ? true : undefined}
              autoComplete="off"
            />
            <Button type="submit" variant="outline" disabled={!input.trim()}>
              Apply
            </Button>
          </div>
          {error ? <FieldError>{error}</FieldError> : null}
          <FieldDescription>
            Fills in the colors, fonts and radius from a code made on{" "}
            <a
              href="https://ui.shadcn.com/create"
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-4"
            >
              ui.shadcn.com/create
            </a>
            .
          </FieldDescription>
        </Field>
      </form>
    </FieldGroup>
  )
}

/** Settings → Appearance: every change applies to the whole UI at once and is saved. */
export function AppearanceForm() {
  const { appearance, update, saving } = useAppearance()
  const set = (patch: Partial<Appearance>) =>
    update({ ...appearance, ...patch })

  const base = BASES.find((b) => b.id === appearance.base_color)
  const themeOptions: Option[] = [
    { id: appearance.base_color, label: "Match base", swatch: base?.swatch },
    ...THEMES.filter((t) => !t.matchesBase).map((t) => ({
      id: t.id,
      label: label(t.id),
      swatch: t.swatch,
    })),
  ]
  const baseChart = CHARTS.find((c) => c.id === appearance.base_color)
  const chartOptions: Option[] = [
    { id: "neutral", label: "Match theme" },
    ...(baseChart
      ? [{ id: baseChart.id, label: "Base", swatch: baseChart.swatch }]
      : []),
    ...CHARTS.filter((c) => !c.matchesBase).map((c) => ({
      id: c.id,
      label: label(c.id),
      swatch: c.swatch,
    })),
  ]

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Colors</CardTitle>
          <CardDescription>
            {saving
              ? "Saving…"
              : "Changes apply right away and follow your account to other browsers."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel id="mode-label">Mode</FieldLabel>
              <ToggleGroup
                aria-labelledby="mode-label"
                value={[appearance.mode]}
                onValueChange={(v: string[]) =>
                  v[0] && set({ mode: v[0] as Appearance["mode"] })
                }
                variant="outline"
                size="sm"
                spacing={0}
              >
                <ToggleGroupItem value="light">
                  <SunIcon data-icon="inline-start" />
                  Light
                </ToggleGroupItem>
                <ToggleGroupItem value="dark">
                  <MoonIcon data-icon="inline-start" />
                  Dark
                </ToggleGroupItem>
                <ToggleGroupItem value="system">
                  <MonitorIcon data-icon="inline-start" />
                  System
                </ToggleGroupItem>
              </ToggleGroup>
            </Field>
            <Field>
              <FieldLabel id="base-label">Base color</FieldLabel>
              <SwatchPicker
                id="base-label"
                options={BASES.map((b) => ({
                  id: b.id,
                  label: label(b.id),
                  swatch: b.swatch,
                }))}
                value={appearance.base_color}
                onChange={(id) => update((current) => withBase(current, id))}
              />
              <FieldDescription>
                Backgrounds, borders and muted text.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel id="theme-label">Theme</FieldLabel>
              <SwatchPicker
                id="theme-label"
                options={themeOptions}
                value={appearance.theme}
                onChange={(id) => set({ theme: id })}
              />
              <FieldDescription>
                Buttons, focus rings and links.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel id="chart-label">Charts</FieldLabel>
              <SwatchPicker
                id="chart-label"
                options={chartOptions}
                value={appearance.chart_color}
                onChange={(id) => set({ chart_color: id })}
              />
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Typography and shape</CardTitle>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="font">Font</FieldLabel>
              <FontSelect
                id="font"
                value={appearance.font}
                onChange={(font) => set({ font })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="font-heading">Heading font</FieldLabel>
              <FontSelect
                id="font-heading"
                inherit
                value={appearance.font_heading}
                onChange={(font_heading) => set({ font_heading })}
              />
            </Field>
            <Field>
              <FieldLabel id="radius-label">Radius</FieldLabel>
              <SwatchPicker
                id="radius-label"
                options={RADII.map((r) => ({
                  id: r.id,
                  label: `${label(r.id)} · ${r.value === "0" ? "0" : r.value}`,
                }))}
                value={appearance.radius}
                onChange={(radius) => set({ radius })}
              />
            </Field>
            <Field>
              <FieldLabel>Style</FieldLabel>
              <p className="text-sm">
                Nova, with Lucide icons{" "}
                <span className="text-muted-foreground">
                  · switching styles is coming in a later version
                </span>
              </p>
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preset code</CardTitle>
          <CardDescription>
            A shadcn preset code captures these settings in a few characters.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PresetCode appearance={appearance} update={update} />
        </CardContent>
      </Card>
    </div>
  )
}
