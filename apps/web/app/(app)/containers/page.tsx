"use client"

import { Skeleton } from "@workspace/ui/components/skeleton"

import { useCapabilities } from "@/components/capabilities-provider"
import { ContainersTable } from "@/components/containers/containers-table"
import { RuntimeEmpty } from "@/components/containers/runtime-empty"

export default function ContainersPage() {
  const { manifest } = useCapabilities()
  if (!manifest) return <Skeleton className="h-40 w-full" />

  const containers = manifest.capabilities.find((c) => c.id === "containers")
  if (!containers?.available) return <RuntimeEmpty capability={containers} />
  return <ContainersTable />
}
