/**
 * Typed client for the Athena API.
 *
 * `schema.d.ts` is generated from the server's OpenAPI schema. Never edit it by hand.
 * Regenerate with `pnpm gen:api` from the repo root after changing server routes.
 * CI fails if it's out of date.
 */
import createClient from "openapi-fetch"

import type { components, paths } from "./schema.js"

export type { components, paths }
export type Schemas = components["schemas"]

/**
 * The API is same-origin: in production FastAPI serves the UI, and in development
 * `next dev` proxies /api to the server.
 */
export const api = createClient<paths>({ baseUrl: "" })
