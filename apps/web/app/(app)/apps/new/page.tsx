"use client"

import { NewAppForm } from "@/components/apps/new-app-form"
import { RequireContainers } from "@/components/containers/require-containers"

export default function NewAppPage() {
  return (
    <RequireContainers>
      <NewAppForm />
    </RequireContainers>
  )
}
