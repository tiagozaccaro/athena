"use client"

import * as React from "react"
import { CpuIcon } from "lucide-react"

import { Button } from "@workspace/ui/components/button"

import {
  useCapabilities,
  type Capability,
} from "@/components/capabilities-provider"
import type {
  ProviderEditing,
  ProviderKind,
} from "@/components/settings/ai-provider-dialog"

export type LocalAiServer = { capability: Capability; kind: ProviderKind }

/**
 * Local AI servers detected on this host and answering (`ai.ollama` and
 * `ai.local.*` in the capability manifest), each with the provider kind that
 * talks to it. A server Athena couldn't name has the "openai-compatible" kind.
 */
export function useLocalAiServers(kinds: ProviderKind[]): LocalAiServer[] {
  const { manifest } = useCapabilities()
  return React.useMemo(() => {
    const out: LocalAiServer[] = []
    for (const c of manifest?.capabilities ?? []) {
      if (c.status !== "ready") continue
      if (c.id !== "ai.ollama" && !c.id.startsWith("ai.local.")) continue
      const kind = kinds.find((k) => k.id === c.provider)
      if (kind) out.push({ capability: c, kind })
    }
    return out
  }, [manifest, kinds])
}

/** One sentence naming what runs here, for an empty state. */
export function localServersSentence(servers: LocalAiServer[]): string {
  const names = servers.map((s) => s.capability.label)
  const list =
    names.length > 1
      ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
      : names[0]
  return `${list} ${names.length > 1 ? "are" : "is"} running on this server. Their models run on your own hardware and nothing leaves the server.`
}

/** The provider form for a detected server, filled in with where it answers. */
export function editingFor(server: LocalAiServer): ProviderEditing {
  const { capability, kind } = server
  return {
    kind,
    values: capability.endpoint ? { base_url: capability.endpoint } : undefined,
    // A server Athena couldn't name: "OpenAI-compatible server on port 8000".
    name: kind.id === "openai-compatible" ? capability.label : undefined,
  }
}

/** A "Use … on this server" button per detected server. */
export function LocalServerButtons({
  servers,
  onUse,
}: {
  servers: LocalAiServer[]
  onUse: (server: LocalAiServer) => void
}) {
  return servers.map((s) => (
    <Button
      key={s.capability.id}
      onClick={() => onUse(s)}
      className="h-auto min-h-8 text-center whitespace-normal"
    >
      <CpuIcon />
      {buttonLabel(s)}
    </Button>
  ))
}

function buttonLabel({ capability, kind }: LocalAiServer): string {
  if (kind.id !== "openai-compatible")
    return `Use ${capability.label} on this server`
  const port = capability.endpoint ? new URL(capability.endpoint).port : ""
  return port ? `Use the AI server on port ${port}` : "Use this AI server"
}
