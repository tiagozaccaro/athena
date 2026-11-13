"use client"

import { Skeleton } from "@workspace/ui/components/skeleton"

import { useCapabilities } from "@/components/capabilities-provider"
import { RuntimeEmpty } from "@/components/containers/runtime-empty"

/** Renders children only when the container runtime is ready; otherwise Start/setup. */
export function RequireContainers({ children }: { children: React.ReactNode }) {
  const { manifest } = useCapabilities()
  if (!manifest) return <Skeleton className="h-40 w-full" />
  const containers = manifest.capabilities.find((c) => c.id === "containers")
  if (!containers?.available) return <RuntimeEmpty capability={containers} />
  return <>{children}</>
}
