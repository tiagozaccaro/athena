"use client"

import * as React from "react"

import { api, errorMessage } from "@workspace/api-client"

/** Pieces of 8 MB: small enough for any proxy, big enough to keep requests few. */
const CHUNK = 8 * 1024 * 1024

export type UploadStatus =
  "queued" | "uploading" | "done" | "error" | "cancelled"

export type Upload = {
  id: string
  file: File
  location: number
  folder: string
  sent: number
  status: UploadStatus
  error?: string
  /** The name was taken; retrying with `overwrite` replaces the file. */
  conflict?: boolean
  overwrite?: boolean
}

/**
 * crypto.randomUUID() only exists on HTTPS or localhost, and Athena is usually opened
 * over plain HTTP on the LAN; getRandomValues works everywhere.
 */
function uploadId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(12))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")
}

type PieceResult = {
  data?: { received: number }
  error?: unknown
  response: Response
}

/** Where the pieces go. The default is the file manager's /api/files/upload. */
export type UploadTransport = {
  send: (u: Upload, offset: number, piece: Blob) => Promise<PieceResult>
  cancel: (u: Upload) => Promise<unknown>
}

const binary = {
  bodySerializer: (b: unknown) => b as Blob,
  headers: { "Content-Type": "application/octet-stream" },
}

const filesTransport: UploadTransport = {
  send: (u, offset, piece) =>
    api.POST("/api/files/upload", {
      params: {
        query: {
          location: u.location,
          path: u.folder,
          name: u.file.name,
          upload_id: u.id,
          offset,
          total: u.file.size,
          overwrite: u.overwrite ?? false,
        },
      },
      body: piece as unknown as string,
      ...binary,
    }),
  cancel: (u) =>
    api.DELETE("/api/files/upload", {
      params: {
        query: { location: u.location, path: u.folder, upload_id: u.id },
      },
    }),
}

/** Uploads through a share link (POST /api/public/shares/{token}/upload). */
export function shareTransport(token: string): UploadTransport {
  return {
    send: (u, offset, piece) =>
      api.POST("/api/public/shares/{token}/upload", {
        params: {
          path: { token },
          query: {
            name: u.file.name,
            upload_id: u.id,
            offset,
            total: u.file.size,
          },
        },
        body: piece as unknown as string,
        ...binary,
      }),
    cancel: (u) =>
      api.DELETE("/api/public/shares/{token}/upload", {
        params: { path: { token }, query: { upload_id: u.id } },
      }),
  }
}

/**
 * A queue of chunked uploads, one file at a time. `onUploaded` runs after each
 * finished file so the listing can refresh.
 */
export function useUploads(
  onUploaded: (location: number, folder: string) => void,
  transport: UploadTransport = filesTransport
) {
  const [uploads, setUploads] = React.useState<Upload[]>([])
  const queue = React.useRef<Upload[]>([])
  const running = React.useRef(false)
  const cancelled = React.useRef(new Set<string>())
  const onUploadedRef = React.useRef(onUploaded)
  onUploadedRef.current = onUploaded
  const transportRef = React.useRef(transport)
  transportRef.current = transport
  const listRef = React.useRef<Upload[]>([])
  listRef.current = uploads

  const update = React.useCallback((id: string, patch: Partial<Upload>) => {
    setUploads((list) =>
      list.map((u) => (u.id === id ? { ...u, ...patch } : u))
    )
  }, [])

  const sendOne = React.useCallback(
    async (u: Upload) => {
      update(u.id, { status: "uploading", sent: 0, error: undefined })
      const size = u.file.size
      let offset = 0
      do {
        if (cancelled.current.has(u.id)) {
          await transportRef.current.cancel(u)
          update(u.id, { status: "cancelled" })
          return
        }
        const piece = u.file.slice(offset, offset + CHUNK)
        const { data, error, response } = await transportRef.current.send(
          u,
          offset,
          piece
        )
        if (!data) {
          update(u.id, {
            status: "error",
            error: errorMessage(
              error,
              `Upload failed (HTTP ${response.status})`
            ),
            conflict: response.status === 409 && offset === 0,
          })
          return
        }
        offset = data.received
        update(u.id, { sent: offset })
      } while (offset < size)
      update(u.id, { status: "done", sent: size })
      onUploadedRef.current(u.location, u.folder)
    },
    [update]
  )

  const pump = React.useCallback(async () => {
    if (running.current) return
    running.current = true
    try {
      for (
        let next = queue.current.shift();
        next;
        next = queue.current.shift()
      ) {
        try {
          await sendOne(next)
        } catch (err) {
          update(next.id, {
            status: "error",
            error: err instanceof Error ? err.message : String(err),
          })
        }
      }
    } finally {
      running.current = false
    }
  }, [sendOne, update])

  const add = React.useCallback(
    (files: File[], location: number, folder: string) => {
      const added = files.map<Upload>((file) => ({
        id: uploadId(),
        file,
        location,
        folder,
        sent: 0,
        status: "queued",
      }))
      queue.current.push(...added)
      setUploads((list) => [...list, ...added])
      void pump()
    },
    [pump]
  )

  /** Try a failed upload again; `overwrite` replaces a file with the same name. */
  const retry = React.useCallback(
    (id: string, overwrite = false) => {
      const found = listRef.current.find((u) => u.id === id)
      if (!found) return
      const again: Upload = {
        ...found,
        id: uploadId(),
        status: "queued",
        sent: 0,
        error: undefined,
        conflict: false,
        overwrite,
      }
      queue.current.push(again)
      setUploads((list) => list.map((u) => (u.id === id ? again : u)))
      void pump()
    },
    [pump]
  )

  const cancel = React.useCallback((id: string) => {
    const queued = queue.current.findIndex((u) => u.id === id)
    if (queued >= 0) {
      queue.current.splice(queued, 1)
      setUploads((list) =>
        list.map((u) => (u.id === id ? { ...u, status: "cancelled" } : u))
      )
    } else {
      cancelled.current.add(id)
    }
  }, [])

  /** Forget finished, failed and cancelled uploads. */
  const clear = React.useCallback(() => {
    setUploads((list) =>
      list.filter((u) => u.status === "queued" || u.status === "uploading")
    )
  }, [])

  return { uploads, add, retry, cancel, clear }
}
