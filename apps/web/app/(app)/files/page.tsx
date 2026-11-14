"use client"

import * as React from "react"

import { Skeleton } from "@workspace/ui/components/skeleton"

import { FilesView } from "@/components/files/files-view"

export default function FilesPage() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <React.Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <FilesView />
    </React.Suspense>
  )
}
