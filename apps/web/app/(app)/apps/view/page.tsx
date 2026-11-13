"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"

import { Skeleton } from "@workspace/ui/components/skeleton"

import { AppDetail } from "@/components/apps/app-detail"
import { RequireContainers } from "@/components/containers/require-containers"

// Static export has no dynamic routes, so the app name is a query parameter.
function View() {
  const name = useSearchParams().get("name") ?? ""
  return <AppDetail key={name} name={name} />
}

export default function AppViewPage() {
  return (
    <RequireContainers>
      <React.Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <View />
      </React.Suspense>
    </RequireContainers>
  )
}
