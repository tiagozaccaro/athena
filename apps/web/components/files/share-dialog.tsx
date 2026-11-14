"use client"

import * as React from "react"
import Link from "next/link"

import { api, errorMessage } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Separator } from "@workspace/ui/components/separator"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import {
  LinkActions,
  LinkBadges,
  type ShareLink,
  shareUrl,
} from "@/components/files/share-links"
import { copyText } from "@/lib/clipboard"

export type ShareTarget = {
  location: number
  path: string
  name: string
  kind: "dir" | "file" | "other"
}

const MODES = [
  { value: "read", label: "View and download" },
  { value: "upload", label: "Upload only (a drop box)" },
]
const EXPIRY = [
  { value: "0", label: "Never" },
  { value: "1", label: "In 1 day" },
  { value: "7", label: "In 7 days" },
  { value: "30", label: "In 30 days" },
]

/** Links to one file or folder: the existing ones, and a form for a new one. */
export function ShareDialog({
  target,
  onClose,
}: {
  target: ShareTarget | null
  onClose: () => void
}) {
  const [links, setLinks] = React.useState<ShareLink[] | null>(null)
  const [mode, setMode] = React.useState("read")
  const [password, setPassword] = React.useState("")
  const [days, setDays] = React.useState("0")
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    if (!target) return
    const { data } = await api.GET("/api/shares", {
      params: { query: { location: target.location, path: target.path } },
    })
    setLinks(data ?? [])
  }, [target])

  React.useEffect(() => {
    setLinks(null)
    setMode("read")
    setPassword("")
    setDays("0")
    setError(null)
    void load()
  }, [load])

  async function create(event: React.FormEvent) {
    event.preventDefault()
    if (!target) return
    setPending(true)
    setError(null)
    const expires = Number(days)
      ? new Date(Date.now() + Number(days) * 86_400_000).toISOString()
      : null
    const { data, error } = await api.POST("/api/shares", {
      body: {
        location: target.location,
        path: target.path,
        mode: mode as ShareLink["mode"],
        password: password || null,
        expires_at: expires,
      },
    })
    setPending(false)
    if (!data) {
      setError(errorMessage(error))
      return
    }
    setPassword("")
    await load()
    const copied = await copyText(shareUrl(data))
    toast.add({
      type: "success",
      title: "Link created",
      description: copied ? "It's copied to the clipboard." : undefined,
    })
  }

  const isFolder = target?.kind === "dir"

  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="truncate">Share {target?.name}</DialogTitle>
          <DialogDescription>
            Anyone with a link can use it without an Athena account. Links use
            the address you opened Athena with.
          </DialogDescription>
        </DialogHeader>

        {links === null ? (
          <Skeleton className="h-12 w-full" />
        ) : links.length ? (
          <ul className="flex flex-col gap-2" aria-label="Links">
            {links.map((link) => (
              <li
                key={link.id}
                className="flex items-center gap-2 rounded-lg border p-2"
              >
                <div className="min-w-0 flex-1">
                  <LinkBadges link={link} />
                </div>
                <LinkActions link={link} onRemoved={() => void load()} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No links yet.</p>
        )}

        <Separator />

        <form id="new-share" onSubmit={create}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="share-mode">What visitors can do</FieldLabel>
              <Select
                items={MODES}
                value={mode}
                onValueChange={(v) => v && setMode(v)}
                disabled={!isFolder}
              >
                <SelectTrigger id="share-mode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {MODES.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <FieldDescription>
                {!isFolder
                  ? "Upload links need a folder."
                  : mode === "upload"
                    ? "Visitors can add files but can't see what's there."
                    : "Visitors can browse, preview and download."}
              </FieldDescription>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="share-password">
                  Password (optional)
                </FieldLabel>
                <Input
                  id="share-password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="share-expiry">Expires</FieldLabel>
                <Select
                  items={EXPIRY}
                  value={days}
                  onValueChange={(v) => v && setDays(v)}
                >
                  <SelectTrigger id="share-expiry" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {EXPIRY.map((e) => (
                        <SelectItem key={e.value} value={e.value}>
                          {e.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </div>
            {error ? <FieldError>{error}</FieldError> : null}
          </FieldGroup>
        </form>

        <DialogFooter>
          <Button
            variant="outline"
            render={<Link href="/files/shares/" />}
            nativeButton={false}
          >
            All links
          </Button>
          <Button type="submit" form="new-share" disabled={pending}>
            {pending ? <Spinner /> : null}
            Create link
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
