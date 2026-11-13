/**
 * Typed client for the Athena API.
 *
 * `schema.d.ts` is generated from the server's OpenAPI schema. Never edit it by hand.
 * Regenerate with `pnpm gen:api` from the repo root after changing server routes.
 * CI fails if it's out of date.
 */
import createClient, { type Middleware } from "openapi-fetch"

import type { components, paths } from "./schema.js"

export type { components, paths }
export type Schemas = components["schemas"]

/**
 * The API is same-origin: in production FastAPI serves the UI, and in development
 * `next dev` proxies /api to the server.
 */
export const api = createClient<paths>({ baseUrl: "" })

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"])

let csrfToken: string | null = null
let unauthorizedHandler: (() => void) | null = null

/** Set after setup/login/status; sent as X-CSRF-Token on every write. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

/** Called when a non-auth request comes back 401 (session expired or signed out elsewhere). */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

const auth: Middleware = {
  onRequest({ request }) {
    if (csrfToken && !SAFE_METHODS.has(request.method)) {
      request.headers.set("X-CSRF-Token", csrfToken)
    }
    return request
  },
  onResponse({ request, response }) {
    const path = new URL(request.url, "http://local").pathname
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      unauthorizedHandler?.()
    }
    return response
  },
}
api.use(auth)

/** A readable message from a FastAPI error body (`detail` string or validation list). */
export function errorMessage(
  error: unknown,
  fallback = "Something went wrong"
): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const item = d as { loc?: unknown[]; msg?: string }
          const field = item.loc?.[item.loc.length - 1]
          const msg = (item.msg ?? "").replace(/^Value error, /, "")
          return field ? `${String(field)}: ${msg}` : msg
        })
        .join(". ")
    }
  }
  return fallback
}
