"use client"

import { RequireContainers } from "@/components/containers/require-containers"
import { StoreBrowser } from "@/components/store/store-browser"

export default function StorePage() {
  return (
    <RequireContainers>
      <StoreBrowser />
    </RequireContainers>
  )
}
