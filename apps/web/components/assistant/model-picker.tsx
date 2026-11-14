"use client"

import * as React from "react"
import { cn } from "@workspace/ui/lib/utils"
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@workspace/ui/components/combobox"

import {
  modelLabel,
  sameModel,
  type ModelRef,
  type ProviderModels,
} from "@/components/assistant/use-models"

type Choice = {
  key: string
  ref: ModelRef
  label: string
  provider: string
  /** False when the provider says the model can't call tools. */
  usable: boolean
  typed?: boolean
}

function choicesFor(providers: ProviderModels[], query: string): Choice[] {
  const out: Choice[] = []
  for (const p of providers) {
    for (const m of p.models) {
      out.push({
        key: `${p.provider_id}/${m.id}`,
        ref: { provider_id: p.provider_id, model: m.id },
        label: m.name && m.name !== m.id ? `${m.name} (${m.id})` : m.id,
        provider: p.provider_name,
        usable: m.tools !== false,
      })
    }
  }
  // Any id can be typed by hand, for each provider (Azure deployments, new models).
  const typed = query.trim()
  if (typed && !out.some((c) => c.ref.model === typed)) {
    for (const p of providers) {
      out.push({
        key: `${p.provider_id}/typed`,
        ref: { provider_id: p.provider_id, model: typed },
        label: `Use “${typed}”`,
        provider: p.provider_name,
        usable: true,
        typed: true,
      })
    }
  }
  return out
}

/**
 * A searchable list of every provider's models (shadcn AI Elements "Model Selector",
 * on a Combobox because providers like OpenRouter list hundreds). Models that can't
 * call tools are shown but can't be picked.
 */
export function ModelPicker({
  providers,
  value,
  onChange,
  variant = "button",
  id,
  className,
}: {
  providers: ProviderModels[] | null
  value: ModelRef | null | undefined
  onChange: (ref: ModelRef) => void
  /** "button" sits in the prompt box; "field" is a full-width form control. */
  variant?: "button" | "field"
  id?: string
  className?: string
}) {
  const [query, setQuery] = React.useState("")
  const items = React.useMemo(
    () => choicesFor(providers ?? [], query),
    [providers, query]
  )
  const selected = items.find((c) => sameModel(c.ref, value)) ?? null
  const label = modelLabel(value, providers)

  return (
    <Combobox
      items={items}
      value={selected}
      onValueChange={(c: Choice | null) => {
        if (c && c.usable) onChange(c.ref)
      }}
      onInputValueChange={setQuery}
      itemToStringLabel={(c: Choice) => `${c.label} ${c.provider}`}
      itemToStringValue={(c: Choice) => c.key}
      filter={(c: Choice, q: string) =>
        !!c.typed ||
        `${c.ref.model} ${c.label} ${c.provider}`
          .toLowerCase()
          .includes(q.toLowerCase())
      }
    >
      <ComboboxTrigger
        id={id}
        aria-label={`Model: ${label}`}
        className={cn(
          "inline-flex min-w-0 items-center gap-1.5 rounded-md text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          variant === "button"
            ? "h-7 max-w-56 px-2 text-muted-foreground hover:bg-muted hover:text-foreground"
            : "h-9 w-full justify-between border border-input bg-transparent px-3 dark:bg-input/30",
          className
        )}
      >
        <span className="truncate">{label}</span>
      </ComboboxTrigger>
      <ComboboxContent
        className="w-80 max-w-[calc(100vw-2rem)]"
        side={variant === "button" ? "top" : "bottom"}
        align={variant === "button" ? "end" : "start"}
      >
        <ComboboxInput
          showTrigger={false}
          placeholder="Search or type a model id"
        />
        <ComboboxEmpty>
          {providers?.length
            ? "No model matches."
            : "Add a provider in Settings → AI first."}
        </ComboboxEmpty>
        <ComboboxList>
          {(c: Choice) => (
            <ComboboxItem key={c.key} value={c} disabled={!c.usable}>
              <span className="min-w-0 flex-1 truncate">{c.label}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {c.usable ? c.provider : "can't use tools"}
              </span>
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  )
}
