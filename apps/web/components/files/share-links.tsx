"use client"

import * as React from "react"
import {
  CopyIcon,
  DownloadIcon,
  LockIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
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
import { toast } from "@workspace/ui/components/toast"

import { copyText } from "@/lib/clipboard"

export type ShareLink = Schemas["ShareOut"]

/** The full link, using the address this page was opened with. */
export function shareUrl(link: ShareLink): string {
  return `${window.location.origin}${link.url_path}`
}

export async function copyLink(link: ShareLink) {
  const ok = await copyText(shareUrl(link))
  toast.add(
    ok
      ? { type: "success", title: "Link copied" }
      : { type: "error", title: "Couldn't copy the link" }
  )
}

export function expiryText(link: ShareLink): string {
  if (link.expired) return "Expired"
  if (!link.expires_at) return "Never expires"
  return `Expires ${new Date(link.expires_at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })}`
}

/** Mode, password and expiry badges for a link. */
export function LinkBadges({ link }: { link: ShareLink }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge variant="secondary">
        {link.mode === "upload" ? <UploadIcon /> : <DownloadIcon />}
        {link.mode === "upload" ? "Upload only" : "View and download"}
      </Badge>
      {link.has_password ? (
        <Badge variant="outline">
          <LockIcon />
          Password
        </Badge>
      ) : null}
      <Badge variant={link.expired ? "destructive" : "outline"}>
        {expiryText(link)}
      </Badge>
      {link.kind === null ? <Badge variant="destructive">Missing</Badge> : null}
    </div>
  )
}

/** Copy and Remove buttons; Remove asks first. */
export function LinkActions({
  link,
  onRemoved,
}: {
  link: ShareLink
  onRemoved: () => void
}) {
  const [confirming, setConfirming] = React.useState(false)

  async function remove() {
    const { error, response } = await api.DELETE("/api/shares/{share_id}", {
      params: { path: { share_id: link.id } },
    })
    setConfirming(false)
    if (response.ok) {
      toast.add({ type: "success", title: "Link removed" })
      onRemoved()
    } else {
      toast.add({
        type: "error",
        title: "Couldn't remove the link",
        description: errorMessage(error),
      })
    }
  }

  return (
    <div className="flex shrink-0 items-center gap-1">
      <Button
        variant="outline"
        size="sm"
        onClick={() => void copyLink(link)}
        aria-label={`Copy link to ${link.name}`}
      >
        <CopyIcon />
        <span className="hidden sm:inline">Copy link</span>
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => setConfirming(true)}
        aria-label={`Remove link to ${link.name}`}
      >
        <Trash2Icon />
      </Button>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this link?</AlertDialogTitle>
            <AlertDialogDescription>
              Anyone with the link to {link.name} loses access. The files stay
              where they are.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => void remove()}
            >
              Remove link
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
