"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"

import { Skeleton } from "@workspace/ui/components/skeleton"

import { RequireContainers } from "@/components/containers/require-containers"
import { StoreAppView } from "@/components/store/store-app-view"

// Static export has no dynamic routes, so the app is identified by query params.
function View() {
  const params = useSearchParams()
  const catalog = params.get("catalog") ?? "builtin"
  const id = params.get("id") ?? ""
  return <StoreAppView key={`${catalog}/${id}`} catalog={catalog} id={id} />
}

export default function StoreAppPage() {
  return (
    <RequireContainers>
      <React.Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <View />
      </React.Suspense>
    </RequireContainers>
  )
}
