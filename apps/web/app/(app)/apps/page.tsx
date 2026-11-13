"use client"

import Link from "next/link"
import { PlusIcon } from "lucide-react"

import { Button } from "@workspace/ui/components/button"

import { AppsGrid } from "@/components/apps/apps-grid"
import { RequireContainers } from "@/components/containers/require-containers"

export default function AppsPage() {
  return (
    <RequireContainers>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            Apps are compose projects that Athena manages.
          </p>
          <Button render={<Link href="/apps/new/" />}>
            <PlusIcon data-icon="inline-start" />
            New app
          </Button>
        </div>
        <AppsGrid />
      </div>
    </RequireContainers>
  )
}
