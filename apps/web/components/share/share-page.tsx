"use client"

import * as React from "react"
import {
  DownloadIcon,
  FileIcon,
  LinkIcon,
  LockIcon,
  UploadIcon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import { cn } from "@workspace/ui/lib/utils"

import { type FileEntry, iconOf } from "@/components/files/file-utils"
import { UploadsPanel } from "@/components/files/uploads-panel"
import { shareTransport, useUploads } from "@/components/files/use-uploads"
import { SharedFolder } from "@/components/share/shared-folder"
import { MediaPreview, shareDownloadUrl } from "@/components/share/share-utils"
import { formatBytes } from "@/lib/format"

type PublicShare = Schemas["PublicShare"]
type State =
  | { status: "loading" }
  | { status: "ok"; share: PublicShare }
  | { status: "error"; code: number; message: string }

/** The token from /s/<token>/. */
function tokenFromPath(): string {
  const parts = window.location.pathname.split("/").filter(Boolean)
  return parts[0] === "s" && parts[1] ? decodeURIComponent(parts[1]) : ""
}

/** What /s/<token> shows: a password prompt, a file, a folder, or a drop box. */
export function SharePage() {
  const [token, setToken] = React.useState<string | null>(null)
  const [state, setState] = React.useState<State>({ status: "loading" })

  const load = React.useCallback(async (t: string) => {
    if (!t) {
      setState({
        status: "error",
        code: 404,
        message: "This link is incomplete.",
      })
      return
    }
    const { data, error, response } = await api.GET(
      "/api/public/shares/{token}",
      { params: { path: { token: t } } }
    )
    if (data) setState({ status: "ok", share: data })
    else
      setState({
        status: "error",
        code: response.status,
        message: errorMessage(error),
      })
  }, [])

  React.useEffect(() => {
    const t = tokenFromPath()
    setToken(t)
    void load(t)
  }, [load])

  if (state.status === "loading" || token === null) {
    return <Skeleton className="h-48 w-full" />
  }
  if (state.status === "error") {
    return (
      <Empty className="border bg-card">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <LinkIcon />
          </EmptyMedia>
          <EmptyTitle>
            {state.code === 410
              ? "This link has expired"
              : state.code === 404
                ? "This link doesn't work"
                : "Couldn't open this link"}
          </EmptyTitle>
          <EmptyDescription>
            {state.code === 410
              ? "Ask whoever sent it for a new one."
              : state.message}
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  const share = state.share
  if (share.locked) {
    return <Unlock token={token} onUnlocked={() => void load(token)} />
  }
  if (share.mode === "upload") {
    return <DropBox token={token} share={share} />
  }
  if (share.kind === "dir") {
    return <SharedFolder token={token} share={share} />
  }
  return <SharedFile token={token} share={share} />
}

function Unlock({
  token,
  onUnlocked,
}: {
  token: string
  onUnlocked: () => void
}) {
  const [password, setPassword] = React.useState("")
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    const { error, response } = await api.POST(
      "/api/public/shares/{token}/unlock",
      { params: { path: { token } }, body: { password } }
    )
    setPending(false)
    if (response.ok) onUnlocked()
    else setError(errorMessage(error))
  }

  return (
    <Card className="mx-auto w-full max-w-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LockIcon className="size-4" />
          This link has a password
        </CardTitle>
        <CardDescription>Enter it to see what&apos;s shared.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit}>
          <FieldGroup>
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="share-password">Password</FieldLabel>
              <Input
                id="share-password"
                type="password"
                autoComplete="current-password"
                autoFocus
                value={password}
                aria-invalid={error ? true : undefined}
                onChange={(e) => setPassword(e.target.value)}
              />
              {error ? <FieldError>{error}</FieldError> : null}
            </Field>
            <Button type="submit" disabled={pending || !password}>
              {pending ? <Spinner /> : null}
              Open
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function SharedFile({ token, share }: { token: string; share: PublicShare }) {
  const entry: FileEntry = {
    name: share.name ?? "file",
    path: "",
    kind: "file",
    size: share.size,
    modified: share.modified,
    is_link: false,
    hidden: false,
  }
  const Icon = iconOf(entry)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex min-w-0 items-center gap-2">
          <Icon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{entry.name}</span>
        </CardTitle>
        <CardDescription>
          {share.size != null ? formatBytes(share.size) : null}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <MediaPreview entry={entry} src={shareDownloadUrl(token, "", true)} />
        <Button
          className="self-start"
          nativeButton={false}
          render={<a href={shareDownloadUrl(token, "")} download />}
        >
          <DownloadIcon />
          Download
        </Button>
      </CardContent>
    </Card>
  )
}

function DropBox({ token, share }: { token: string; share: PublicShare }) {
  const transport = React.useMemo(() => shareTransport(token), [token])
  const uploads = useUploads(() => {}, transport)
  const input = React.useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = React.useState(false)

  function add(files: FileList | File[] | null) {
    if (files?.length) uploads.add(Array.from(files), { location: 0 }, "")
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Send files to {share.name}</CardTitle>
        <CardDescription>
          Files you add are uploaded right away. You can&apos;t see what others
          have sent, and nothing you send replaces another file.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            "flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground transition-colors",
            dragging && "border-primary bg-primary/5"
          )}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            add(e.dataTransfer.files)
          }}
        >
          <FileIcon className="size-8" />
          <p>Drop files here, or</p>
          <Button onClick={() => input.current?.click()}>
            <UploadIcon />
            Choose files
          </Button>
          <input
            ref={input}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              add(e.target.files)
              e.target.value = ""
            }}
          />
        </div>
      </CardContent>
      <UploadsPanel
        uploads={uploads.uploads}
        onCancel={uploads.cancel}
        onRetry={uploads.retry}
        onClear={uploads.clear}
      />
    </Card>
  )
}
