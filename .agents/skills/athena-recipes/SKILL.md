---
name: athena-recipes
description: Step-by-step recipes with exact files and commands for the most common Athena changes - a new API endpoint, a database table or column (Alembic migration), a new page with a sidebar entry, calling the API from the UI, a long-running job, a host-wide setting, and a new test. Use whenever you're about to make one of these changes and aren't sure of the project's exact conventions, before guessing.
---

# Athena recipes

Each recipe lists the files to touch, in order. Copy the existing example it names instead of inventing a new shape. When unsure about a library's API, look it up (the Context7 MCP server for library docs, the `shadcn` skill or MCP for UI components, `apps/web/node_modules/next/dist/docs/` for Next 16). Don't guess.

Paths below are relative to `apps/server/src/athena/` (server) or `apps/web/` (web) unless they start with the repo root.

## A. New API endpoint

1. **Router:** add it to the area's router in `api/<area>.py`. A new area gets a new file, with `router = APIRouter(prefix="/<area>", tags=["<area>"])`.
   - Every route needs an explicit, unique `operation_id` in camelCase: `@router.get("/system", operation_id="getSystemSettings")`.
   - Request and response bodies are Pydantic models in the same file. Return the model; don't return dicts.
   - Session dependencies come from `athena.auth.deps`: `user: Authed`, `db: DbSession`. For admin-only, check `user.user.is_admin` and raise 403 (see `set_system` in `api/settings.py`).
   - Errors: `raise HTTPException(status.HTTP_409_CONFLICT, "Readable message")`. The UI shows the message as is, so write it for a person.
2. **Register:** a new router goes in `main.py`: `app.include_router(<area>.router, prefix="/api", dependencies=[require_user])`. Never leave a router public; only health, `/api/auth/*` and the public share route are.
3. **Privileged action?** Call `audit.record(db, user.user.username, "<area>.<action>", target)`.
4. **Test:** in `apps/server/tests/test_<area>.py`:
   ```python
   from conftest import make_app, signed_in
   from fastapi.testclient import TestClient

   def test_thing(tmp_path):
       with TestClient(make_app(tmp_path)) as client:
           signed_in(client)                 # creates the admin and sets the X-CSRF-Token header
           r = client.get("/api/<area>/...")
           assert r.status_code == 200

   def test_thing_needs_a_session(tmp_path):
       with TestClient(make_app(tmp_path)) as client:
           assert client.get("/api/<area>/...").status_code == 401
   ```
   Also test the failure case (404, 409 or 403). `make_app` uses a fake macOS host (`FakeProbe(os="darwin")`); pass `store=` to simulate another OS (see `tests/fake_probe.py`).
5. **Client:** run `pnpm gen:api` from the repo root and commit `packages/api-client/`. Never hand-write request types.
6. **Check:** `scripts/check.sh`.

## B. Database table or column

1. **Model:** edit `db/models.py` (SQLModel).
2. **Migration:** add `db/migrations/versions/<NNNN>_<what>.py`. Copy the latest file there and change `revision` to the next number, `down_revision` to the previous one, and the `upgrade()` / `downgrade()` bodies. Use `op.create_table`, `op.add_column` and `sa.Column(..., sqlmodel.sql.sqltypes.AutoString(length=N))`, matching how the model declares the field. New columns on existing tables need a `server_default` or `nullable=True`, because the table already has rows.
3. **Prove it:** `cd apps/server && uv run pytest -q tests/test_db.py`. `test_models_match_migrations` prints the exact difference if the model and migration disagree. Migrations run on every server start.

## C. New page with a sidebar entry

1. **Page:** `app/(app)/<route>/page.tsx` stays tiny and renders a view component:
   ```tsx
   import { ThingView } from "@/components/<area>/thing-view"
   export default function ThingPage() { return <ThingView /> }
   ```
   There are no dynamic routes (static export). Detail pages use query params read with `useSearchParams()` (see `app/(app)/apps/view/page.tsx`, opened as `/apps/view/?name=x`).
2. **View:** `components/<area>/thing-view.tsx` with `"use client"`. Build it from shadcn components in `@workspace/ui/components/*`: Card, Table, Tabs, Empty, Alert, Skeleton. Search the registry before writing custom UI. Use theme tokens only (`text-muted-foreground`, `bg-card`), never raw colors.
3. **Gating:** if the feature depends on the host, read `useCapability("<id>")`, and render `Empty` with the capability's `detail` when it's missing. Containers pages wrap in `<RequireContainers>`.
4. **Sidebar:** add a `NavItem` in `components/nav.ts` with a lucide icon and `capability` if it's host-dependent. Add it only once the page exists.
5. **Verify:** `pnpm lint && pnpm typecheck && pnpm build`, then the `athena-ui-verify` skill (release build, phone width, dark mode).

## D. Calling the API from the UI

```tsx
import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { toast } from "@workspace/ui/components/toast"
import { useApi } from "@/hooks/use-api"

// Simple read: useApi gives { status: "loading" } | { status: "ok", data } | { status: "error", error }
const things = useApi(() => api.GET("/api/<area>"))
// A list that must refresh after actions: write a small hook with a load() callback,
// like components/apps/use-apps-list.ts, and call load() after every action.

const { data, error } = await api.POST("/api/<area>/{name}/start", {
  params: { path: { name } },
  body: { force: false },
})
if (error) toast.add({ type: "error", title: "Couldn't start", description: errorMessage(error) })
else void load()                                             // always refresh lists after an action
```

The client adds the CSRF header and handles 401 (redirect to `/login/`) by itself. Show errors next to the field or in a toast, never silently. A working example is `components/packages/manager-panel.tsx`.

## E. Long-running operation (job)

- **Server:** `body` is `async def body(job: Job) -> None`. Inside it, `await run_or_fail(job, argv, "Install jq", env=...)` runs a command and streams its output (raising `CommandFailedError` on a non-zero exit), and `await job.log("line")` adds your own lines. Start it with `job = request.app.state.jobs.start(title, body)` and return `job.out()` with status 202. Allow one job per resource at a time (see `_start` in `api/packages.py` and `app.state.package_jobs` in `main.py`).
- **Web:** keep the returned job in state and render `<JobDialog job={job} />`. It streams the output over SSE and shows the final status.
- **Test:** enter the `TestClient` as a context manager for the whole test, or the job's event loop is closed (see `client_for` in `tests/test_packages_api.py`).

## F. Host-wide setting (admin only)

1. Add a field with a safe default to `SystemSettings` in `system_settings.py`. Stored JSON is validated on load, and unknown or invalid values fall back to defaults, so no migration is needed.
2. If changing it has side effects (like closing terminals), handle that in `set_system` in `api/settings.py` and audit it.
3. Add the control on Settings → System (`app/(app)/settings/`), then run `pnpm gen:api`.

## G. Anything that touches the host OS

Stop and use the `athena-platform-feature` skill: capability id, detection, provider, registry, gated UI and fixtures.

## H. Before you say "done"

- [ ] `scripts/check.sh` passes, and `packages/api-client` is regenerated and committed if the API changed.
- [ ] New code has tests, including a failure case.
- [ ] UI changes are verified in a browser (`athena-ui-verify`).
- [ ] New dependency → license row in `docs/mvp-design.md` §9. Design change → §11 row.
- [ ] PR opened with auto-merge, and CI plus CodeQL are green (`athena-ship`).
- [ ] `docs/STATUS.md` updated; new lessons added to `docs/AGENT-NOTES.md`.
