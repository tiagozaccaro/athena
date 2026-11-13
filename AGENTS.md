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

## Layout (planned)

- `apps/web`: Next.js, static export (`output: "export"`), shadcn/ui. Served by the Python server in production.
- `packages/ui`: shadcn components. Athena-made components go in `packages/ui/src/components/athena/`.
- `packages/api-client`: TS client generated from the server's OpenAPI. Don't hand-write request types.
- `apps/server`: Python (uv), FastAPI, SQLite. Package `athena`.
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
