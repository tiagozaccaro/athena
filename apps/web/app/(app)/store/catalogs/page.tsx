"use client"

import { RequireContainers } from "@/components/containers/require-containers"
import { CatalogsManager } from "@/components/store/catalogs-manager"

export default function CatalogsPage() {
  return (
    <RequireContainers>
      <CatalogsManager />
    </RequireContainers>
  )
}
