# Athena status

_Shared handoff log for every coding agent. Update it at the end of each session (see AGENTS.md → Handoff)._

**Current milestone:** M1 (platform + capabilities), in progress. Part 1 (capabilities) is in PR `feat/m1-capabilities`; part 2 (database + auth) is next.

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

## In progress

- M1 part 2: SQLite + migrations, the admin account, sessions, CSRF, `/setup` and `/login`.
- Not yet verified: a real `athena service install` on any OS (only dry runs), and real capability detection on Linux and Windows hosts (only CI and fakes).

## Next

M1, platform + capabilities (see `docs/mvp-design.md` §3 and §10):
1. First-run setup wizard (`/setup`), admin account (argon2), session cookie, CSRF, and `/login`. Wire up `NavUser` (`apps/web/components/nav-user.tsx`).
2. SQLite plus migrations (SQLModel and Alembic).

## Open questions

- Should the first-run wizard suggest a cloud AI provider or local Ollama first? (`docs/mvp-design.md` §12)

## Blockers

- The release PR needs a `RELEASE_PLEASE_TOKEN` repo secret (a fine-grained PAT with contents + pull-requests write on this repo). Without it, CI doesn't run on release-please PRs, and they can only be merged with admin bypass.
