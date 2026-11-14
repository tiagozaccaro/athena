"use client"

import * as React from "react"

import { api, type Schemas } from "@workspace/api-client"

export type ProviderModels = Schemas["ProviderModels"]
export type ModelRef = Schemas["ModelRef"]

/** Every provider's models, for the model pickers. `reload()` after provider changes. */
export function useModels() {
  const [providers, setProviders] = React.useState<ProviderModels[] | null>(
    null
  )
  const load = React.useCallback(async () => {
    const { data } = await api.GET("/api/assistant/models")
    setProviders(data ?? [])
  }, [])
  React.useEffect(() => {
    void load()
  }, [load])
  return { providers, reload: load }
}

export function sameModel(a?: ModelRef | null, b?: ModelRef | null): boolean {
  return !!a && !!b && a.provider_id === b.provider_id && a.model === b.model
}

/** "claude-x · Anthropic", or the bare id when the provider is gone. */
export function modelLabel(
  ref: ModelRef | null | undefined,
  providers: ProviderModels[] | null
): string {
  if (!ref) return "Pick a model"
  const provider = providers?.find((p) => p.provider_id === ref.provider_id)
  const info = provider?.models.find((m) => m.id === ref.model)
  return info?.name || ref.model
}
