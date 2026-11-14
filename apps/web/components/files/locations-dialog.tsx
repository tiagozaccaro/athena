"use client"

import * as React from "react"
import { PencilIcon, PlusIcon, Trash2Icon } from "lucide-react"

import { api, errorMessage } from "@workspace/api-client"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemTitle,
} from "@workspace/ui/components/item"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import type { Location } from "@/components/files/file-utils"

type Editing = { id: number | null; name: string; path: string }

function LocationForm({
  editing,
  onCancel,
  onSaved,
}: {
  editing: Editing
  onCancel: () => void
  onSaved: () => void
}) {
  const [name, setName] = React.useState(editing.name)
  const [path, setPath] = React.useState(editing.path)
  const [error, setError] = React.useState<string | null>(null)
  const [pending, setPending] = React.useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    const body = { name, path }
    const result =
      editing.id === null
        ? await api.POST("/api/files/locations", { body })
        : await api.PUT("/api/files/locations/{location_id}", {
            params: { path: { location_id: editing.id } },
            body,
          })
    setPending(false)
    if (result.data) onSaved()
    else setError(errorMessage(result.error))
  }

  return (
    <form onSubmit={submit} className="rounded-lg border p-4">
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="location-name">Name</FieldLabel>
          <Input
            id="location-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Media"
            maxLength={64}
            required
          />
        </Field>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="location-path">Folder on the server</FieldLabel>
          <Input
            id="location-path"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/srv/media"
            className="font-mono"
            required
            aria-invalid={error ? true : undefined}
          />
          {error ? <FieldError>{error}</FieldError> : null}
        </Field>
        <Field orientation="horizontal">
          <Button type="submit" disabled={pending}>
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {editing.id === null ? "Add location" : "Save"}
          </Button>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        </Field>
      </FieldGroup>
    </form>
  )
}

/** Add, change and remove the folders the file manager can reach. Admins only. */
export function LocationsDialog({
  open,
  locations,
  onOpenChange,
  onChanged,
}: {
  open: boolean
  locations: Location[]
  onOpenChange: (open: boolean) => void
  onChanged: () => void
}) {
  const [editing, setEditing] = React.useState<Editing | null>(null)
  const [removing, setRemoving] = React.useState<number | null>(null)

  async function remove(loc: Location) {
    setRemoving(loc.id)
    const { error, response } = await api.DELETE(
      "/api/files/locations/{location_id}",
      { params: { path: { location_id: loc.id } } }
    )
    setRemoving(null)
    if (response.ok) {
      toast.add({
        type: "success",
        title: `Removed ${loc.name}`,
        description: "The folder and its files are still on the server.",
      })
      onChanged()
    } else {
      toast.add({
        type: "error",
        title: `Couldn't remove ${loc.name}`,
        description: errorMessage(error),
      })
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setEditing(null)
        onOpenChange(o)
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Locations</DialogTitle>
          <DialogDescription>
            The file manager only reaches these folders. Removing one
            doesn&apos;t touch its files.
          </DialogDescription>
        </DialogHeader>
        <ItemGroup className="max-h-80 gap-2 overflow-y-auto">
          {locations.map((loc) => (
            <Item key={loc.id} variant="outline" size="sm">
              <ItemContent className="min-w-0">
                <ItemTitle>
                  {loc.name}
                  {!loc.available ? (
                    <Badge variant="destructive">Missing</Badge>
                  ) : !loc.writable ? (
                    <Badge variant="secondary">Read-only</Badge>
                  ) : null}
                </ItemTitle>
                <ItemDescription className="truncate font-mono text-xs">
                  {loc.path}
                </ItemDescription>
              </ItemContent>
              <ItemActions>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Edit ${loc.name}`}
                  onClick={() =>
                    setEditing({ id: loc.id, name: loc.name, path: loc.path })
                  }
                >
                  <PencilIcon />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${loc.name}`}
                  disabled={removing === loc.id}
                  onClick={() => remove(loc)}
                >
                  {removing === loc.id ? <Spinner /> : <Trash2Icon />}
                </Button>
              </ItemActions>
            </Item>
          ))}
        </ItemGroup>
        {editing ? (
          <LocationForm
            key={editing.id ?? "new"}
            editing={editing}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setEditing(null)
              onChanged()
            }}
          />
        ) : (
          <Button
            variant="outline"
            className="self-start"
            onClick={() => setEditing({ id: null, name: "", path: "" })}
          >
            <PlusIcon />
            Add location
          </Button>
        )}
      </DialogContent>
    </Dialog>
  )
}
