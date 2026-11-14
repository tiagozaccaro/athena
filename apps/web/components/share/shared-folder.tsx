"use client"

import * as React from "react"
import { DownloadIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@workspace/ui/components/breadcrumb"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"

import {
  type FileEntry,
  formatModified,
  iconOf,
  previewOf,
} from "@/components/files/file-utils"
import { MediaPreview, shareDownloadUrl } from "@/components/share/share-utils"
import { formatBytes } from "@/lib/format"

type Listing = Schemas["Listing"]

/** A shared folder: browse, preview media, download files or everything as a zip. */
export function SharedFolder({
  token,
  share,
}: {
  token: string
  share: Schemas["PublicShare"]
}) {
  const [path, setPath] = React.useState("")
  const [listing, setListing] = React.useState<Listing | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [preview, setPreview] = React.useState<FileEntry | null>(null)

  React.useEffect(() => {
    setListing(null)
    setError(null)
    api
      .GET("/api/public/shares/{token}/list", {
        params: { path: { token }, query: { path } },
      })
      .then(({ data, error }) => {
        if (data) setListing(data)
        else setError(errorMessage(error))
      })
  }, [token, path])

  const crumbs = path ? path.split("/") : []

  function open(entry: FileEntry) {
    if (entry.kind === "dir") setPath(entry.path)
    else if (previewOf(entry) && previewOf(entry) !== "text") setPreview(entry)
    else window.location.href = shareDownloadUrl(token, entry.path)
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-card p-4 text-card-foreground">
      <div className="flex flex-wrap items-center gap-2">
        <Breadcrumb className="min-w-0 flex-1">
          <BreadcrumbList>
            <BreadcrumbItem>
              {crumbs.length ? (
                <BreadcrumbLink
                  render={<button type="button" onClick={() => setPath("")} />}
                >
                  {share.name}
                </BreadcrumbLink>
              ) : (
                <BreadcrumbPage>{share.name}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
            {crumbs.map((name, i) => {
              const target = crumbs.slice(0, i + 1).join("/")
              return (
                <React.Fragment key={target}>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem className="min-w-0">
                    {i === crumbs.length - 1 ? (
                      <BreadcrumbPage className="truncate">
                        {name}
                      </BreadcrumbPage>
                    ) : (
                      <BreadcrumbLink
                        render={
                          <button
                            type="button"
                            onClick={() => setPath(target)}
                          />
                        }
                      >
                        {name}
                      </BreadcrumbLink>
                    )}
                  </BreadcrumbItem>
                </React.Fragment>
              )
            })}
          </BreadcrumbList>
        </Breadcrumb>
        <Button
          variant="outline"
          nativeButton={false}
          render={<a href={shareDownloadUrl(token, path)} download />}
        >
          <DownloadIcon />
          Download all
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Couldn&apos;t open this folder</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : listing === null ? (
        <Skeleton className="h-40 w-full" />
      ) : listing.entries.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground">
          This folder is empty.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="hidden text-right sm:table-cell">
                Size
              </TableHead>
              <TableHead className="hidden md:table-cell">Modified</TableHead>
              <TableHead className="w-0">
                <span className="sr-only">Download</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {listing.entries.map((entry) => {
              const Icon = iconOf(entry)
              return (
                <TableRow key={entry.path}>
                  <TableCell className="max-w-0">
                    <button
                      type="button"
                      className="flex w-full min-w-0 items-center gap-2 text-left hover:underline"
                      onClick={() => open(entry)}
                    >
                      <Icon className="size-4 shrink-0 text-muted-foreground" />
                      <span className="truncate">{entry.name}</span>
                    </button>
                  </TableCell>
                  <TableCell className="hidden text-right text-muted-foreground tabular-nums sm:table-cell">
                    {entry.size != null ? formatBytes(entry.size) : "—"}
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">
                    {formatModified(entry.modified)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      nativeButton={false}
                      aria-label={`Download ${entry.name}`}
                      render={
                        <a
                          href={shareDownloadUrl(token, entry.path)}
                          download
                        />
                      }
                    >
                      <DownloadIcon />
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      <Dialog
        open={preview !== null}
        onOpenChange={(o) => !o && setPreview(null)}
      >
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle className="truncate">{preview?.name}</DialogTitle>
          </DialogHeader>
          {preview ? (
            <MediaPreview
              entry={preview}
              src={shareDownloadUrl(token, preview.path, true)}
            />
          ) : null}
          <DialogFooter>
            {preview ? (
              <Button
                nativeButton={false}
                render={
                  <a href={shareDownloadUrl(token, preview.path)} download />
                }
              >
                <DownloadIcon />
                Download
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
