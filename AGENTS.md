# Athena

Self-hosted home server control panel (CasaOS-style) for **Linux, macOS and Windows**.

This file is the single source of instructions for every coding agent working here (Claude Code, OpenCode, Hermes Agent and others). `CLAUDE.md` only imports this file. Don't put agent-specific rules anywhere else.

## Start here (every session, every agent)

1. Read `docs/STATUS.md`: the current milestone, what's done, what's in progress, and what's next.
2. Read the rules file of the app you'll touch: `apps/server/AGENTS.md` or `apps/web/AGENTS.md`.
3. Read `docs/AGENT-NOTES.md`: how the maintainer works, the command cheat sheet, patterns to copy, and the gotchas earlier sessions already hit (Windows CI, CodeQL, Base UI, wsgidav, …).
4. Read the parts of `docs/mvp-design.md` that the task touches. It holds the design and the decisions log (§11).
5. Before ending a session, update `docs/STATUS.md` (see [Handoff](#handoff)). The next agent may be a different tool with no memory of yours.

## Git workflow (mandatory)

The repo is public at `github.com/tiagozaccaro/athena`. `main` is protected: no direct pushes, no force pushes.

1. Start every task on a new branch from an up-to-date `main`: `git switch main && git pull && git switch -c <type>/<short-description>`. Types: `feat`, `fix`, `perf`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `revert`.
2. Commit on the branch. Never commit to or push `main`.
3. Open a PR to `main` with a Conventional Commit title (`feat(store): add install form`). CI checks the title, because it becomes the squash commit and the changelog entry.
4. Turn on auto-merge right after opening the PR, without asking: `gh pr merge <n> --squash --auto --delete-branch`. This is the maintainer's standing instruction for every PR. CI (`ci-ok`) and `pr-title` must pass. PRs are squash-merged and the branch is deleted. Exceptions: release-please PRs (the maintainer merges those) and PRs whose base isn't `main` (turn it on once they're retargeted to `main`).
5. Don't edit `CHANGELOG.md` or `version.txt` by hand. release-please manages them.

Full details are in `CONTRIBUTING.md`.

## Layout

Each app has its own rules file. **Read it before working there**: some agents load it automatically, others won't.

- `apps/server`: Python 3.13 (uv), FastAPI, package and CLI `athena`. Rules, module map and test conventions are in **`apps/server/AGENTS.md`**.
- `apps/web`: Next.js 16 static export, shadcn/ui on Base UI (preset `b0`), served by the Python server in production. Rules, layout and UI conventions are in **`apps/web/AGENTS.md`**.
- `packages/ui`: shadcn components (`pnpm dlx shadcn@latest add <name> -c apps/web`). Athena-made components go in `packages/ui/src/components/athena/`.
- `packages/api-client`: generated from the server's OpenAPI schema with `pnpm gen:api`. Never hand-write request types; CI fails if the client is out of date.
- `catalog/`: built-in app store (compose + `x-athena` metadata, see `catalog/README.md`).
- `scripts/`: `install.sh` and `install.ps1` (the one-line installers, attached to every GitHub release; keep them in sync with the server's `athena service` CLI), `check.sh` (CI's checks locally), `check-docs.mjs`, `build-wheel.sh`, `agents-sync.mjs`, `gen-theme-css.mjs`, and `scripts/e2e/` (the browser smoke test).
- `.github/`: CI (`ci.yml`), E2E (`e2e.yml`), PR title check, release-please (`release.yml`), Dependabot, templates.

## Rules

- **Cross-platform first.** Anything that touches the host goes through a provider and a capability in the manifest. The UI and the AI assistant only show what the host supports. Follow the `athena-platform-feature` skill.
- **Don't guess APIs.** Read the existing feature that does something similar, then the library's docs (Context7, the `shadcn` skill or MCP, Next's bundled docs). Training data is often older than the versions used here (Next 16, Base UI, xterm.js 6, Python 3.13).
- **Open-source dependencies only.** Record licenses in `docs/mvp-design.md` §9.
- **shadcn first.** Search registries (shadcn MCP / `shadcn search`) before building a component, including the `@ai-elements` registry for chat UI. Only create a component when nothing fits.
- **App shell** comes from the `dashboard-01` block without its demo data, demo page, or demo content components.
- **Theming.** Use theme tokens only (no raw colors). Base color, theme, chart color, fonts and radius switch at runtime via data attributes. The shadcn style is fixed to preset `b0` for the MVP.
  - `packages/ui/src/styles/themes.css` and `themes.json` are generated from the shadcn registry by `pnpm gen:theme` (`scripts/gen-theme-css.mjs`). Never edit them by hand; rerun after upgrading shadcn. Appearance logic is in `apps/web/lib/appearance.ts`, fonts in `apps/web/lib/fonts.ts`.
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
| Lessons, gotchas, commands | `docs/AGENT-NOTES.md` | ← | ← | ← |

**MCP servers** (`.mcp.json`):
- `shadcn`: browse, search and install registry items.
- `next-devtools`: Next.js docs and runtime diagnostics while `pnpm dev` runs.
- `playwright`: a headless browser with an in-memory profile, for UI verification (navigate, accessibility snapshots, screenshots in `.playwright-mcp/`, clicks, console, network, resize). It uses the system Chrome; on a machine without Chrome, add `--browser firefox` or install Chrome.
- `context7`: current docs and examples for any library (FastAPI, SQLModel, Alembic, wsgidav, xterm.js, Base UI, pydantic-ai, rclone…). Use it before writing code against a library API you aren't sure of. It works without an API key (rate-limited); set `CONTEXT7_API_KEY` for higher limits.

**Skills** (`.agents/skills/`, third-party ones pinned in `skills-lock.json`):
- `shadcn`
- `building-pydantic-ai-agents`, `pydantic-ai-harness`, `pydantic`
- Written for this project:
  - `athena-recipes`: step-by-step for common changes (endpoint, migration, page and nav, API calls, jobs, settings), plus the "before you say done" checklist. **Start here if you're unsure how something is done in this repo.**
  - `athena-platform-feature`: anything that touches the host OS (capabilities, providers).
  - `athena-ui-verify`: browser verification of UI and API changes.
  - `athena-ship`: branch, local checks, PR with auto-merge, CI/CodeQL triage, handoff.
  - `athena-host-test`: real Linux hosts in a Lima VM, and the E2E workflow on GitHub runners.
  - `athena-catalog-app`: adding or updating store apps.

Agents that don't load skills automatically can read them directly: `.agents/skills/<name>/SKILL.md`.

**Changing tooling:**
- *Add an MCP server:* edit `.mcp.json`, then run `node scripts/agents-sync.mjs` to regenerate `opencode.json` and the Hermes snippet. Never edit the `mcp` block of `opencode.json` by hand.
- *Add a third-party skill:* `npx skills add <owner/repo> --skill <name> -a claude-code -y`. It lands in `.agents/skills/` through the symlink and is recorded in `skills-lock.json`.
- *Add a project skill:* create `.agents/skills/<name>/SKILL.md` with `name` and `description` frontmatter.
- *Restore skills on a new machine:* `npx skills experimental_install`.

**One-time setup per agent:**
- **Every agent and person:** `git config core.hooksPath .githooks` turns on the pre-push check (see [Definition of done](#definition-of-done)).
- **Claude Code:** nothing else to do. On Windows, enable symlinks in git (`git config core.symlinks true` with Developer Mode on) so `.claude/skills` works.
- **OpenCode:** nothing to do. `opencode.json` is committed.
- **Hermes Agent:** run `node scripts/agents-sync.mjs --hermes`. It trusts this repo's skills (`hermes skills trust`) and adds any missing MCP servers to `~/.hermes/config.yaml` through `hermes mcp add`. Then restart Hermes or run `/reload-mcp`. `--hermes-print` only prints the YAML block.
  - Known gap: Hermes's skill scanner rates `pydantic-ai-harness` as "dangerous" and hides it. That's a false positive from its docs mentioning `~/.ssh`, `os.environ` and command denylists. Hermes agents should read `.agents/skills/pydantic-ai-harness/SKILL.md` directly when working on the assistant.

## Definition of done

Before pushing, run `scripts/check.sh` (the same checks as CI; `--quick` skips the web build). Windows-only failures still show up only in CI.

Turn on the pre-push hook once per clone so this happens even when you forget: `git config core.hooksPath .githooks`. It runs only the parts the push touches: about 2 s for docs, under a minute with server changes. Skip it once with `git push --no-verify`.

**Docs are checked too.** `node scripts/check-docs.mjs` (in CI and in `scripts/check.sh`) fails when AGENTS.md, `docs/AGENT-NOTES.md`, `catalog/README.md` or a project skill names a file, function, component or constant that doesn't exist. When you rename something, fix the docs in the same PR. To mention something on purpose that doesn't exist (an old name, an external API), end the line with `<!-- docs-check: ignore -->`.

### UI work

Any change to `apps/web`, or to an API the UI uses, is verified in a real browser with the `athena-ui-verify` skill (release build on port 8421, fresh data dir, happy path plus a failure, console and network checks, phone width and dark mode, cleanup) before it's reported as done.

## Handoff

At the end of every session, update `docs/STATUS.md`:
- Move finished items to **Done**, with the commit or PR if there is one.
- Under **In progress**, say exactly where you stopped: files touched, what works, what's broken, and the next concrete step.
- Add new **Open questions** or **Blockers**.
- Keep it short. Detail belongs in the design doc, commits and code.

If you learned something non-obvious, add it to `docs/AGENT-NOTES.md`. That covers a CI failure with a surprising cause, a tool quirk, a scanner false positive, or a pattern worth copying.

Don't rely on agent-private memory (Claude memory, Hermes MEMORY.md, OpenCode sessions) for anything another agent needs.
