"use client"

import * as React from "react"
import { ExternalLinkIcon } from "lucide-react"

import type { Schemas } from "@workspace/api-client"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import { Checkbox } from "@workspace/ui/components/checkbox"
import { Field, FieldLabel } from "@workspace/ui/components/field"

type AppOut = Schemas["AppOut"]

export function AppStatusBadge({ app }: { app: AppOut }) {
  switch (app.status) {
    case "running":
      return <Badge variant="secondary">Running</Badge>
    case "partial":
      return (
        <Badge variant="outline">
          {app.running}/{app.total} running
        </Badge>
      )
    case "stopped":
      return <Badge variant="outline">Stopped</Badge>
    default:
      return <Badge variant="outline">Not deployed</Badge>
  }
}

/** Host ports from "8080→80/tcp" entries, deduplicated, TCP only. */
export function webPorts(app: AppOut): string[] {
  const ports = app.ports
    .filter((p) => p.endsWith("/tcp"))
    .map((p) => p.split("→")[0] ?? "")
  return [...new Set(ports)].filter(Boolean)
}

/** "Open" links to the app's published ports on the host Athena is served from. */
export function OpenLinks({ app }: { app: AppOut }) {
  const ports = webPorts(app)
  if (app.status === "stopped" || app.status === "not_deployed") return null
  return (
    <>
      {ports.map((port) => (
        <Button
          key={port}
          variant="outline"
          size="sm"
          render={
            <a
              href={`${window.location.protocol}//${window.location.hostname}:${port}`}
              target="_blank"
              rel="noreferrer"
            />
          }
        >
          <ExternalLinkIcon data-icon="inline-start" />
          {ports.length > 1 ? `:${port}` : "Open"}
        </Button>
      ))}
    </>
  )
}

export function DeleteAppDialog({
  name,
  onCancel,
  onConfirm,
}: {
  name: string | null
  onCancel: () => void
  onConfirm: (deleteData: boolean) => void
}) {
  const [deleteData, setDeleteData] = React.useState(false)
  React.useEffect(() => setDeleteData(false), [name])

  return (
    <AlertDialog
      open={name !== null}
      onOpenChange={(open) => !open && onCancel()}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove {name}?</AlertDialogTitle>
          <AlertDialogDescription>
            Its containers are stopped and removed, and Athena forgets the app.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Field orientation="horizontal">
          <Checkbox
            id="delete-data"
            checked={deleteData}
            onCheckedChange={(checked) => setDeleteData(checked === true)}
          />
          <FieldLabel htmlFor="delete-data" className="font-normal">
            Also delete its volumes and data folder. This can&apos;t be undone.
          </FieldLabel>
        </Field>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => name && onConfirm(deleteData)}
          >
            Remove
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
