"use client"

import { ContainersTable } from "@/components/containers/containers-table"
import { RequireContainers } from "@/components/containers/require-containers"

export default function ContainersPage() {
  return (
    <RequireContainers>
      <ContainersTable />
    </RequireContainers>
  )
}
