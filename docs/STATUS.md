# Athena status

_Shared handoff log for every coding agent. Update it at the end of each session (see AGENTS.md → Handoff)._

**Current milestone:** M0 (monorepo skeleton), not started

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
  - release-please for versions and CHANGELOG.md, Dependabot for Actions.
  - Install scripts (`scripts/install.sh`, `scripts/install.ps1`).
  - `main` protected: PR + CI required, squash-only.

## In progress

_Nothing._

## Next

M0 (see `docs/mvp-design.md` §5.1 and §10):
1. `pnpm dlx shadcn@latest init --preset b0 --template next` and pick the monorepo option. That creates `apps/web` and `packages/ui`.
2. `pnpm dlx shadcn@latest add dashboard-01 -c apps/web`, then strip the demo files (§5.2).
3. Create `apps/server` with uv (FastAPI, `athena` package, `/api/health`), and set Next to `output: "export"`.
4. Add Turborepo tasks and `packages/api-client` generated from OpenAPI.
5. CI already has `web` and `server` jobs that switch on when `pnpm-lock.yaml` and `apps/server/pyproject.toml` exist. Check that they pass.
6. Add `npm` and `uv` to `.github/dependabot.yml`, add `python` to CodeQL, and build and upload the server wheel in `release.yml`.
7. Implement `athena service install|uninstall --data-dir --port`, which the install scripts call. Switch release-please to the `python` release type, or keep `simple` with `extra-files`.

## Open questions

- Should the first-run wizard suggest a cloud AI provider or local Ollama first? (`docs/mvp-design.md` §12)
- Does the shadcn CLI rewrite `dashboard-01`'s Tabler icons to the preset's icon library? Check during M0.

## Blockers

- The release PR needs a `RELEASE_PLEASE_TOKEN` repo secret (a fine-grained PAT with contents + pull-requests write on this repo). Without it, CI doesn't run on release-please PRs, and they can only be merged with admin bypass.
