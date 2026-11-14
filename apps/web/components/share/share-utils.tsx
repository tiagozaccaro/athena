"use client"

import { type FileEntry, previewOf } from "@/components/files/file-utils"

export function shareBase(token: string): string {
  return `/api/public/shares/${encodeURIComponent(token)}`
}

export function shareDownloadUrl(token: string, path: string, inline = false) {
  const q = new URLSearchParams({ path })
  if (inline) q.set("inline", "true")
  return `${shareBase(token)}/download?${q}`
}

/** Image, video or audio, shown inline; nothing for other files. */
export function MediaPreview({
  entry,
  src,
}: {
  entry: FileEntry
  src: string
}) {
  const kind = previewOf(entry)
  if (kind === "image")
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={entry.name}
        className="max-h-[60dvh] w-full rounded-lg object-contain"
      />
    )
  if (kind === "video")
    return (
      <video src={src} controls className="max-h-[60dvh] w-full rounded-lg" />
    )
  if (kind === "audio") return <audio src={src} controls className="w-full" />
  return null
}
