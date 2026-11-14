import type { LucideIcon } from "lucide-react"
import {
  FileArchiveIcon,
  FileAudioIcon,
  FileCodeIcon,
  FileIcon,
  FileImageIcon,
  FileTextIcon,
  FileVideoIcon,
  FolderIcon,
  LinkIcon,
} from "lucide-react"

import type { Schemas } from "@workspace/api-client"

export type FileEntry = Schemas["FileEntry"]
export type Location = Schemas["LocationOut"]
export type Remote = Schemas["RemoteOut"]

/** Where files live: a location (by id) or a cloud remote (by name). */
export type Source = { location: number } | { remote: string }

export function isRemote(source: Source): source is { remote: string } {
  return "remote" in source
}

/** A string that identifies a source, for Select values and React keys. */
export function sourceKey(source: Source): string {
  return isRemote(source) ? `r:${source.remote}` : `l:${source.location}`
}

export function sourceFromKey(key: string): Source {
  return key.startsWith("r:")
    ? { remote: key.slice(2) }
    : { location: Number(key.slice(2)) }
}

export function sameSource(a: Source, b: Source): boolean {
  return sourceKey(a) === sourceKey(b)
}

/** The source as API query parameters ({location} or {remote}). */
export function sourceQuery(source: Source): Record<string, string> {
  return isRemote(source)
    ? { remote: source.remote }
    : { location: String(source.location) }
}

/** How a file opens in the preview sheet. Matches the server's inline types. */
export type Preview = "image" | "video" | "audio" | "text" | null

const IMAGE = ["png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "ico"]
const VIDEO = ["mp4", "m4v", "webm", "mov"]
const AUDIO = ["mp3", "m4a", "ogg", "oga", "opus", "wav", "flac"]
const ARCHIVE = ["zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar", "zst"]
const CODE = [
  "js",
  "ts",
  "tsx",
  "jsx",
  "json",
  "py",
  "sh",
  "bash",
  "zsh",
  "ps1",
  "go",
  "rs",
  "c",
  "h",
  "cpp",
  "java",
  "rb",
  "php",
  "css",
  "html",
  "xml",
  "toml",
  "ini",
  "yaml",
  "yml",
  "sql",
  "lua",
  "conf",
]
const TEXT = [
  "txt",
  "md",
  "log",
  "csv",
  "tsv",
  "env",
  "cfg",
  "properties",
  "service",
  "gitignore",
  "dockerignore",
  "srt",
  "nfo",
]

export function extension(name: string): string {
  const dot = name.lastIndexOf(".")
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ""
}

export function previewOf(entry: FileEntry): Preview {
  if (entry.kind !== "file") return null
  const ext = extension(entry.name)
  if (IMAGE.includes(ext)) return "image"
  if (VIDEO.includes(ext)) return "video"
  if (AUDIO.includes(ext)) return "audio"
  // Files without an extension are often text (README, Dockerfile, .bashrc).
  if (CODE.includes(ext) || TEXT.includes(ext) || ext === "") return "text"
  return null
}

export function iconOf(entry: FileEntry): LucideIcon {
  if (entry.kind === "dir") return FolderIcon
  if (entry.kind === "other") return LinkIcon
  const ext = extension(entry.name)
  if (IMAGE.includes(ext)) return FileImageIcon
  if (VIDEO.includes(ext)) return FileVideoIcon
  if (AUDIO.includes(ext)) return FileAudioIcon
  if (ARCHIVE.includes(ext)) return FileArchiveIcon
  if (CODE.includes(ext)) return FileCodeIcon
  if (TEXT.includes(ext)) return FileTextIcon
  return FileIcon
}

/** The parent of an API path ("a/b" → "a", "a" → ""). */
export function parentOf(path: string): string {
  const i = path.lastIndexOf("/")
  return i < 0 ? "" : path.slice(0, i)
}

export function joinPath(folder: string, name: string): string {
  return folder ? `${folder}/${name}` : name
}

/** URL of a file or folder download (`inline` shows media in the browser). Folders
 * on a remote can't be downloaded. */
export function downloadUrl(
  source: Source,
  path: string,
  inline = false
): string {
  const q = new URLSearchParams({ ...sourceQuery(source), path })
  if (inline) q.set("inline", "true")
  return isRemote(source)
    ? `/api/cloud/files/download?${q}`
    : `/api/files/download?${q}`
}

/** Address bar URL for a folder in the file manager (?loc= or ?remote=). */
export function folderHref(source: Source, path: string): string {
  const q = new URLSearchParams(
    isRemote(source)
      ? { remote: source.remote }
      : { loc: String(source.location) }
  )
  if (path) q.set("path", path)
  return `/files/?${q}`
}

export function formatModified(iso: string | null | undefined): string {
  if (!iso) return "—"
  const date = new Date(iso)
  const sameYear = date.getFullYear() === new Date().getFullYear()
  return date.toLocaleString(undefined, {
    year: sameYear ? undefined : "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}
