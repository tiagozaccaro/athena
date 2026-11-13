# Athena status

_Shared handoff log for every coding agent. Update it at the end of each session (see AGENTS.md → Handoff)._

**Current milestone:** M2 (containers + apps), in progress. Part A (runtime, jobs, containers) is in PR `feat/m2-containers`; part B (apps: compose deploy, `docker run` import) is next.

## Done

- MVP design written: `docs/mvp-design.md` (architecture, capability manifest, features, frontend plan, API, licenses, milestones, decisions log).
- Agent tooling shared across Claude Code, OpenCode and Hermes Agent:
  - `AGENTS.md` holds the instructions.
  - `.agents/skills/` holds the skills.
  - `.mcp.json` lists the MCP servers, and `scripts/agents-sync.mjs` generates the other agents' configs from it.
  - Verified on 2026-11-13: OpenCode 2.2.5 connects to shadcn and next-devtools. Hermes 0.23.1 has both servers enabled and loads 4 of 5 project skills; `pydantic-ai-harness` is quarantined by Hermes's scanner as a false positive (see AGENTS.md).
- GitHub setup for the public repo `tiagozaccaro/athena`:
  - Apache-2.0 license, README, CONTRIBUTING, Code of Conduct, SECURITY, issue and PR templates, CODEOWNERS.
  - CI on Linux, macOS and Windows, with a single required check `ci-ok`, plus the `pr-title` check.
  - release-please for versions and CHANGELOG.md, Dependabot.
  - Install scripts (`scripts/install.sh`, `scripts/install.ps1`).
  - `main` protected: PR + CI required, squash-only.
- **M0, monorepo skeleton** (branch `feat/m0-monorepo`):
  - The shadcn Next monorepo is scaffolded with `init --preset b0 --template next --monorepo --base base`: `apps/web`, `packages/ui`, and the eslint and typescript config packages.
  - The `dashboard-01` app shell is in place without its demo data, page or content components. The leftover `@dnd-kit` dependency is removed.
  - The sidebar has Dashboard plus a Help link, the header shows a live server status badge, and the dashboard has a Server card fed by `/api/system/info`.
  - `apps/server` (FastAPI) has `/api/health` and `/api/system/info` and serves the exported UI at `/`. Its `athena` CLI has `serve`, `openapi`, and `service install|uninstall|status` (systemd, launchd or a Scheduled Task, all with `--dry-run`). It has 16 tests.
  - `packages/api-client` is generated from OpenAPI (`pnpm gen:api`), and CI fails on drift.
  - CI runs web lint, typecheck and build, plus server ruff and pytest on 3 OSes, plus a service install dry run.
  - The release workflow builds the UI, bundles it into `athena_server-<v>-py3-none-any.whl` and uploads it with the install scripts. release-please bumps `pyproject.toml` and the `package.json` files.
  - Dependabot covers npm and uv.
  - Verified locally on macOS: the static export served by FastAPI, the `next dev` proxy, the wheel installed with `uv tool install` and serving the UI, and the service install dry run.

- **M1 part 1, capabilities** (branch `feat/m1-capabilities`):
  - `athena/platform/` has a never-raising `Probe` (which, run with timeout, Docker API `/version` ping over a unix socket or Windows named pipe) and per-OS detectors.
  - Detected: containers (Docker Engine or Podman on Linux; Colima or Podman on macOS; WSL Docker, Podman or Rancher Desktop on Windows), package managers for the host's OS only, `terminal.host`, `cloud.rclone`, `files` and `shares.webdav`.
  - Statuses are ready, stopped, missing, unsupported or needs_privilege, with `start`/`setup` actions.
  - `GET /api/system/capabilities` (cached, detected in the background at startup) and `POST …/refresh`.
  - Logging goes to `<data-dir>/logs/athena.log` (rotating) plus stderr.
  - Web: `CapabilitiesProvider` with `useCapabilities()` and `useCapability(id)`, nav items filtered by their `capability`, and a dashboard "Capabilities" card with Re-detect. Package managers that aren't installed are hidden.
  - 40 server tests, using `tests/fake_probe.py` to simulate each OS. Verified on macOS: Colima found, Homebrew ready, rclone missing.

- **M1 part 2, database + auth** (branch `feat/m1-auth`):
  - SQLite at `<data-dir>/athena.db`, with SQLModel models (`users`, `sessions`) and Alembic migrations (`0001`) run on every start. Covered by a model/migration drift test.
  - Auth: one admin created at `/setup`, argon2id passwords, hashed session tokens in an HttpOnly SameSite=Strict cookie, a CSRF header on writes, login throttling (5 per 5 minutes), and no username enumeration.
  - API: `/api/auth/status|setup|login|logout`. Everything else except health requires a session.
  - Web: `AuthProvider` gate (redirects to `/setup/` or `/login/`), the setup and login pages (`CredentialsForm`), `NavUser` in the sidebar footer with Log out, and the API client adds CSRF and handles 401.
  - 56 server tests. Verified in the browser against the built UI: setup (including the mismatch error), the dashboard, logout, a wrong password, login, and a CSRF-protected Re-detect.

- **Admin password recovery** (branch `feat/admin-password-reset`):
  - `athena admin reset-password [--data-dir] [--username] [--password-stdin]` sets a new argon2 hash and deletes all of that account's sessions.
  - It fails clearly with no database, an unknown user, a short password, mismatched prompts, or a permission error (with a sudo hint).
  - The login page and README point to it. 62 server tests.

- Admin password recovery merged (#13); code scanning fix (#14).
- **M2 part A, containers** (branch `feat/m2-containers`):
  - `athena/containers/`: a runtime from the `containers` capability (Docker CLI with `--host <endpoint>`, Podman CLI, or `wsl.exe -e docker`), and a service for list, inspect, start, stop, restart, remove and logs.
  - `athena/jobs.py`: an in-memory job runner with SSE.
  - `audit_log` table (migration 0002), written on container actions and runtime start.
  - API: `/api/containers` (list, get, start, stop, restart, delete, logs, SSE `logs/stream`), `POST /api/containers/runtime/start` (job), `/api/jobs/{id}` and `/events`.
  - Web: a Containers page (table grouped by compose project, actions menu, live logs sheet, remove confirmation), a runtime empty state (Start button with live job progress, or per-OS setup steps), and a Base UI toast. The Containers nav item stays visible when the runtime is stopped or missing.
  - 87 server tests (real-engine lifecycle opt-in: `ATHENA_DOCKER_TESTS=1`, on in Linux CI).
  - Verified on macOS with Colima: list (grouped), live logs (the `logs -f` process is killed on close), stop, remove with toast, audit rows, the stopped-runtime view, and the Start job dialog (with a fake `colima` to avoid touching the real VM).

## In progress

- M2 part A review and merge. Next: part B (apps).
- Not yet verified: a real `athena service install` on any OS (only dry runs), and real capability detection on Linux and Windows hosts (only CI and fakes).

## Next

M2 part B, apps (see `docs/mvp-design.md` §4.1):
1. Athena-managed apps in `<data-dir>/apps/<name>/compose.yaml`, recorded in SQLite.
2. Deploy a pasted or uploaded compose file (validated, with a CodeMirror editor), and import a `docker run` command (shlex + flag map).
3. App lifecycle as jobs: up, down, pull + recreate (update), remove (optionally with volumes).
4. Apps page and app detail page (`/apps/view?name=`), with services, logs and the compose editor.

Later: container stats, Windows path translation for WSL bind mounts.

## Open questions

- Should the first-run wizard suggest a cloud AI provider or local Ollama first? (`docs/mvp-design.md` §12)

## Blockers

- The release PR needs a `RELEASE_PLEASE_TOKEN` repo secret (a fine-grained PAT with contents + pull-requests write on this repo). Without it, CI doesn't run on release-please PRs, and they can only be merged with admin bypass.
