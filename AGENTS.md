# Athena

Self-hosted home server control panel (CasaOS-style) for **Linux, macOS and Windows**.

This file is the single source of instructions for every coding agent working here (Claude Code, OpenCode, Hermes Agent and others). `CLAUDE.md` only imports this file. Don't put agent-specific rules anywhere else.

## Start here (every session, every agent)

1. Read `docs/STATUS.md`: the current milestone, what's done, what's in progress, and what's next.
2. Read the parts of `docs/mvp-design.md` that the task touches. It holds the design and the decisions log (§11).
3. Before ending a session, update `docs/STATUS.md` (see [Handoff](#handoff)). The next agent may be a different tool with no memory of yours.

## Git workflow (mandatory)

The repo is public at `github.com/tiagozaccaro/athena`. `main` is protected: no direct pushes, no force pushes.

1. Start every task on a new branch from an up-to-date `main`: `git switch main && git pull && git switch -c <type>/<short-description>`. Types: `feat`, `fix`, `perf`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `revert`.
2. Commit on the branch. Never commit to or push `main`.
3. Open a PR to `main` with a Conventional Commit title (`feat(store): add install form`). CI checks the title, because it becomes the squash commit and the changelog entry.
4. CI (`ci-ok`) and `pr-title` must pass. PRs are squash-merged and the branch is deleted.
5. Don't edit `CHANGELOG.md` or `version.txt` by hand. release-please manages them.

Full details are in `CONTRIBUTING.md`.

## Layout

- `apps/web`: Next.js 16, static export, shadcn/ui on Base UI (`base-nova` style, preset `b0`, lucide icons). Served by the Python server in production.
  - `next.config.ts` exports statically for `next build` and proxies `/api` to `http://localhost:8420` only in `next dev`, because rewrites aren't allowed with static export.
  - All data loads client-side through `@workspace/api-client`. It adds the CSRF header and redirects to `/login/` on 401. There are no server actions and no dynamic routes; use query params for detail pages.
  - Signed-in pages live under `app/(app)/`, inside `AuthProvider` and then `CapabilitiesProvider`. Use `useAuth()` and `useCapability(id)`. `/setup` and `/login` live under `app/(auth)/`.
  - Code editing: `CodeEditor` from `@workspace/ui/components/athena/code-editor` (CodeMirror 6, themed from CSS variables).
  - Pages that need containers wrap their content in `<RequireContainers>`, which shows Start or setup when the runtime isn't ready.
  - Live output: `useEventStream(url)` (SSE), `<LogView>`, and `<JobDialog job>` for job progress. Notifications use `toast.add({ type, title, description })` from `@workspace/ui/components/toast` (Base UI), not sonner.
  - Next.js 16 differs from older versions. Read `apps/web/AGENTS.md` and the docs in `apps/web/node_modules/next/dist/docs/` before writing Next code.
  - Sidebar entries live in `apps/web/components/nav.ts`. Add a section only when its page exists.
- `packages/ui`: shadcn components (`pnpm dlx shadcn@latest add <name> -c apps/web`). Athena-made components go in `packages/ui/src/components/athena/`.
- `packages/api-client`: generated from the server's OpenAPI schema with `pnpm gen:api`. Never hand-write request types; CI fails if the client is out of date.
- `apps/server`: Python 3.13 (uv), FastAPI, package `athena`, CLI `athena` (`serve`, `openapi`, `service install|uninstall|status`). Tests are in `apps/server/tests`.
  - API routes go under `/api`, each with an explicit `operation_id`. New routers must require a session: `include_router(..., dependencies=[require_user])`. Only health and `/api/auth/*` are public. Writes are CSRF-checked automatically by `require_user`.
  - Database changes need a new Alembic migration in `athena/db/migrations/versions/`. `tests/test_db.py` fails if the models and migrations differ.
  - Host detection lives in `athena/platform/`. Test new detectors with `tests/fake_probe.py`.
  - Containers: `athena/containers/` (`runtime_from(capability)` gives the CLI prefix and client; `service.py` holds the operations). Validate container refs with `check_ref`. Real-engine tests only run with `ATHENA_DOCKER_TESTS=1` (on in Linux CI). Locally they would touch the developer's runtime, so they're opt-in.
  - Apps: `athena/apps/` (`store.py` for the on-disk layout and compose checks, `docker_run.py` for the converter) and `athena/api/apps.py`. Compose commands go through `store.compose(...)` with `env=store.env(name)` so `${ATHENA_APP_DATA}` resolves.
  - Store: `athena/catalog/` (`model.py` is the `x-athena` format, `loader.py` loads catalogs and resolves install values, `registry.py` holds the loaded apps) and `athena/api/store.py`. Installs go through `deploy_new_app()` in `athena/api/apps.py`. Catalog apps live in `catalog/apps/<id>/compose.yaml` (see `catalog/README.md`), and `tests/test_catalog.py` checks every one.
  - Long operations run as jobs (`request.app.state.jobs.start(title, body)`) and stream over SSE. Record privileged actions with `athena.audit.record(...)`.
  - Tests use `conftest.make_app()` and `signed_in(client)`.
- `catalog/`: built-in app store (compose + `x-athena` metadata).
- `scripts/install.sh`, `scripts/install.ps1`: the one-line installers. They're attached to every GitHub release. Keep them in sync with the server's `athena service` CLI.
- `.github/`: CI (`ci.yml`), PR title check, release-please (`release.yml`), Dependabot, templates.

## Rules

- **Cross-platform first.** Anything that touches the host goes through a provider and a capability in the manifest. The UI and the AI assistant only show what the host supports. Follow the `athena-platform-feature` skill.
- **Open-source dependencies only.** Record licenses in `docs/mvp-design.md` §9.
- **shadcn first.** Search registries (shadcn MCP / `shadcn search`) before building a component, including the `@ai-elements` registry for chat UI. Only create a component when nothing fits.
- **App shell** comes from the `dashboard-01` block without its demo data, demo page, or demo content components.
- **Theming.** Use theme tokens only (no raw colors). Base color, theme, chart color, fonts and radius switch at runtime via data attributes. The shadcn style is fixed to preset `b0` for the MVP.
- Run pnpm commands from the repo root; Python commands with `uv run` inside `apps/server`.
- Decisions that change the design go in `docs/mvp-design.md` (update the section and add a row to §11 Decisions log), not only in chat or an agent's private memory.

## Shared agent tooling

Everything agent-related has one source of truth in the repo. Each agent reads it either directly or through a link or generated file.

| What | Source of truth | Claude Code | OpenCode | Hermes Agent |
|---|---|---|---|---|
| Instructions | `AGENTS.md` | `CLAUDE.md` imports it | reads `AGENTS.md` | reads `AGENTS.md` |
| Skills | `.agents/skills/` | `.claude/skills` → symlink | reads `.agents/skills` | reads `.agents/skills` after `hermes skills trust` |
| MCP servers | `.mcp.json` | reads it | `opencode.json` (generated) | `~/.hermes/config.yaml` (snippet generated) |
| Project state | `docs/STATUS.md` | ← | ← | ← |

**MCP servers** (`.mcp.json`):
- `shadcn`: browse, search and install registry items.
- `next-devtools`: Next.js docs and runtime diagnostics while `pnpm dev` runs.

**Skills** (`.agents/skills/`, third-party ones pinned in `skills-lock.json`):
- `shadcn`
- `building-pydantic-ai-agents`, `pydantic-ai-harness`, `pydantic`
- `athena-platform-feature` (written for this project)

**Changing tooling:**
- *Add an MCP server:* edit `.mcp.json`, then run `node scripts/agents-sync.mjs` to regenerate `opencode.json` and the Hermes snippet. Never edit the `mcp` block of `opencode.json` by hand.
- *Add a third-party skill:* `npx skills add <owner/repo> --skill <name> -a claude-code -y`. It lands in `.agents/skills/` through the symlink and is recorded in `skills-lock.json`.
- *Add a project skill:* create `.agents/skills/<name>/SKILL.md` with `name` and `description` frontmatter.
- *Restore skills on a new machine:* `npx skills experimental_install`.

**One-time setup per agent:**
- **Claude Code:** nothing to do. On Windows, enable symlinks in git (`git config core.symlinks true` with Developer Mode on) so `.claude/skills` works.
- **OpenCode:** nothing to do. `opencode.json` is committed.
- **Hermes Agent:** run `node scripts/agents-sync.mjs --hermes`. It trusts this repo's skills (`hermes skills trust`) and adds any missing MCP servers to `~/.hermes/config.yaml` through `hermes mcp add`. Then restart Hermes or run `/reload-mcp`. `--hermes-print` only prints the YAML block.
  - Known gap: Hermes's skill scanner rates `pydantic-ai-harness` as "dangerous" and hides it. That's a false positive from its docs mentioning `~/.ssh`, `os.environ` and command denylists. Hermes agents should read `.agents/skills/pydantic-ai-harness/SKILL.md` directly when working on the assistant.

## Handoff

At the end of every session, update `docs/STATUS.md`:
- Move finished items to **Done**, with the commit or PR if there is one.
- Under **In progress**, say exactly where you stopped: files touched, what works, what's broken, and the next concrete step.
- Add new **Open questions** or **Blockers**.
- Keep it short. Detail belongs in the design doc, commits and code.

Don't rely on agent-private memory (Claude memory, Hermes MEMORY.md, OpenCode sessions) for anything another agent needs.
