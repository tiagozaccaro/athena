"use client"

import * as React from "react"
import { CircleAlertIcon, DownloadIcon, SaveIcon } from "lucide-react"

import { api, errorMessage } from "@workspace/api-client"
import { CodeEditor } from "@workspace/ui/components/athena/code-editor"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Button } from "@workspace/ui/components/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@workspace/ui/components/sheet"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import {
  downloadUrl,
  extension,
  type FileEntry,
  previewOf,
} from "@/components/files/file-utils"
import { formatBytes } from "@/lib/format"

type Text = { content: string; version: string }
type TextState =
  | { status: "loading" }
  | { status: "ok"; text: Text }
  | { status: "error"; error: string }

function TextPreview({
  location,
  entry,
  onSaved,
}: {
  location: number
  entry: FileEntry
  onSaved: () => void
}) {
  const [state, setState] = React.useState<TextState>({ status: "loading" })
  const [draft, setDraft] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    let live = true
    void api
      .GET("/api/files/text", {
        params: { query: { location, path: entry.path } },
      })
      .then(({ data, error }) => {
        if (!live) return
        if (data) {
          setState({ status: "ok", text: data })
          setDraft(data.content)
        } else setState({ status: "error", error: errorMessage(error) })
      })
    return () => {
      live = false
    }
  }, [location, entry.path])

  if (state.status === "loading") return <Skeleton className="h-64 w-full" />
  if (state.status === "error") {
    return (
      <Alert>
        <CircleAlertIcon />
        <AlertTitle>Can&apos;t open this file here</AlertTitle>
        <AlertDescription>
          {state.error} You can still download it.
        </AlertDescription>
      </Alert>
    )
  }

  const changed = draft !== state.text.content
  async function save() {
    if (state.status !== "ok") return
    setSaving(true)
    const { data, error } = await api.PUT("/api/files/text", {
      body: {
        location,
        path: entry.path,
        content: draft,
        version: state.text.version,
      },
    })
    setSaving(false)
    if (data) {
      setState({ status: "ok", text: data })
      toast.add({ type: "success", title: `Saved ${entry.name}` })
      onSaved()
    } else {
      toast.add({
        type: "error",
        title: `Couldn't save ${entry.name}`,
        description: errorMessage(error),
      })
    }
  }

  const ext = extension(entry.name)
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <CodeEditor
        value={draft}
        onChange={setDraft}
        language={ext === "yaml" || ext === "yml" ? "yaml" : "text"}
        minHeight="16rem"
        maxHeight="calc(100dvh - 14rem)"
        aria-label={`Contents of ${entry.name}`}
      />
      <div className="flex justify-end">
        <Button onClick={save} disabled={!changed || saving}>
          {saving ? <Spinner /> : <SaveIcon />}
          Save
        </Button>
      </div>
    </div>
  )
}

/** Shows an image, video, audio or text file; text files can be edited and saved. */
export function FilePreview({
  location,
  entry,
  onClose,
  onSaved,
}: {
  location: number
  entry: FileEntry | null
  onClose: () => void
  onSaved: () => void
}) {
  const kind = entry ? previewOf(entry) : null
  const inline = entry ? downloadUrl(location, entry.path, true) : ""
  return (
    <Sheet open={entry !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="right"
        className="w-full gap-0 data-[side=right]:sm:max-w-3xl"
      >
        <SheetHeader>
          <SheetTitle className="truncate pr-8">{entry?.name}</SheetTitle>
          <SheetDescription>
            {entry?.size != null ? formatBytes(entry.size) : null}
          </SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col overflow-auto px-4">
          {entry && kind === "image" ? (
            // eslint-disable-next-line @next/next/no-img-element -- a host file, not a bundled asset
            <img
              src={inline}
              alt={entry.name}
              className="mx-auto max-h-[calc(100dvh-12rem)] max-w-full rounded-md object-contain"
            />
          ) : null}
          {entry && kind === "video" ? (
            <video
              src={inline}
              controls
              className="max-h-[calc(100dvh-12rem)] w-full rounded-md bg-muted"
            />
          ) : null}
          {entry && kind === "audio" ? (
            <audio src={inline} controls className="w-full" />
          ) : null}
          {entry && kind === "text" ? (
            <TextPreview
              key={entry.path}
              location={location}
              entry={entry}
              onSaved={onSaved}
            />
          ) : null}
          {entry && kind === null ? (
            <p className="text-sm text-muted-foreground">
              There&apos;s no preview for this kind of file.
            </p>
          ) : null}
        </div>
        <SheetFooter>
          {entry ? (
            <Button
              variant="outline"
              nativeButton={false}
              render={<a href={downloadUrl(location, entry.path)} download />}
            >
              <DownloadIcon />
              Download
            </Button>
          ) : null}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
