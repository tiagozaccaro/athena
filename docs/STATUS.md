# Athena status

_Shared handoff log for every coding agent. Update it at the end of each session (see AGENTS.md → Handoff)._

**Current milestone:** M5 (packages + terminal). M4 is done (#20, #21, #22). Part A, package managers, is in PR `feat/m5-packages`; part B (host terminal + container exec) is next.

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

- **M2 part B, apps** (branch `feat/m2-apps`):
  - `apps` table (migration 0003).
  - `athena/apps/store.py`: layout `<data-dir>/apps/<name>/compose.yaml` plus `compose.prev.yaml` plus `data/`; compose structural checks; `ATHENA_APP_DATA` env.
  - `athena/apps/docker_run.py`: a `docker run` to compose converter with ~45 flags, combined short flags, line continuations and warnings.
  - API `/api/apps`: list (status from container labels), get (compose plus containers), convert, validate (`compose config`), create (202 job: config, pull, up), PUT (edit and redeploy), `/{start|stop|restart|update}`, DELETE (`?delete_data=`). One job per app; all audited.
  - Web: Apps grid (status, Open links per published port, actions), New app (name, CodeMirror compose editor, upload, docker run tab with Convert and warnings, Validate, Deploy with live job), app detail `/apps/view/?name=` (actions, containers with logs, compose editor with Save and redeploy), `RequireContainers` gate, Apps nav item.
  - 116 server tests (real app lifecycle opt-in, on in Linux CI). Verified on Colima in the browser: convert, validate, deploy (live pull), served on :18080, stop, edit port and redeploy (on :18081, `compose.prev.yaml` kept), remove, and remove with data (`--volumes`, folder deleted, audit "with data").
  - Fixed during verification: actions and delete now pass `ATHENA_APP_DATA`; the job dialog stays visible after removing the last app; `runtime_from` looks up `docker` at call time (macOS CI has no docker CLI).

- M2 merged: containers (#15) and apps (#16).
- **M3 part A, store** (branch `feat/m3-store`):
  - Catalog format: compose plus `x-athena`, with install values in `.env` via `${KEY}`, default tokens, and generated secrets.
  - `catalog/` holds 20 curated apps (Jellyfin, Vaultwarden, Home Assistant, Uptime Kuma, AdGuard Home, Nextcloud, Syncthing, FreshRSS, Forgejo, Navidrome, Audiobookshelf, Paperless-ngx, File Browser, code-server, Node-RED, Mealie, Stirling-PDF, IT Tools, Memos, qBittorrent). Every image tag was checked against its registry, and every app passes `docker compose config`.
  - `athena/catalog/`: model, loader (resolves and validates install values), registry.
  - `/api/store`: categories, apps (search and filter, showing installed copies), app detail (form fields with resolved defaults, suggested name), and install (422 with per-field errors, then a deploy job).
  - The `apps.catalog_id` column (migration 0004), and apps report a `web_port` for "Open".
  - Web: a Store page (search, category toggles, icon cards with fallbacks), a store app page (details, notes, read-only compose, install form with typed fields and an Advanced section), and a Store nav item.
  - The wheel bundles `catalog/` (release workflow plus an artifact check).
  - 138 server tests. Verified on Colima: browse, a bad-port error, a Forgejo install from the store (running, single Open link :3002, `.env` mode 600), and removal. An IT Tools install failed on Docker Hub's anonymous pull rate limit, and the failure is reported clearly in the job dialog.

- **Agent UI verification** (#19): the Playwright MCP server (headless, isolated) in `.mcp.json`, synced to OpenCode and Hermes and enabled for Claude Code; the `athena-ui-verify` skill. Verified that OpenCode connects, Hermes has it enabled and loads the skill, and all 12 tools the skill names exist.
- **M3 part B, remote catalogs** (#18):
  - `athena/catalog/remote.py`: repo URL to archive URL, safe tar/zip extraction, finds `apps/` or `Apps/` when nested, normalizes the catalog, atomic swap.
  - `athena/catalog/casaos.py`: the CasaOS to Athena converter (YAML 1.2 booleans).
  - `catalogs` table (migration 0005); the registry reloads built-in plus downloaded catalogs.
  - `/api/store/catalogs`: list, add (job), refresh (job), remove. `StoreApp.catalog_name`.
  - `PUT /api/apps/{name}/env`: edit `.env` and redeploy. `AppDetail.env`.
  - Web: `/store/catalogs` (list, refresh, remove, one-click CasaOS AppStore, add form), a Catalogs button and source badges in the Store, and an app Settings tab (`.env` editor).
  - 163 server tests (CasaOS fixtures from 3 real apps). Verified: the official CasaOS release zip imports 182 apps, all passing `compose config`. In the browser: one-click add, search across catalogs, an imported app's form, and the Forgejo Settings tab changing the port 3002 to 3003 (redeployed, Open link updated).

- **M4 step 1, live host stats** (#20):
  - `athena/monitor.py`: `HostMonitor` samples psutil every 2 s (1 h ring buffer), with disks refreshed every 30 s. Disk filtering and de-duplication per OS (APFS volumes collapse to `/`), and network totals skip loopback and container bridges.
  - API: `GET /api/system/stats` (snapshot + history) and `GET /api/system/stats/stream` (SSE `stats` events). The monitor starts in the app lifespan.
  - `athena serve` now has a 5 s graceful-shutdown timeout. Found in verification: an open SSE stream kept the server from stopping at all.
  - Web: `HostStatsProvider` (snapshot, then SSE; reloads the snapshot after a reconnect), CPU/memory/network/disk-activity cards with 5 min / 1 h sparklines and a Live/Reconnecting badge, Storage card (shadcn `progress`), Temperatures card (only when reported), and uptime on the Server card. `recharts` added to `apps/web`.
  - 179 server tests. Verified in the browser on macOS: live updates, the range toggle, stopping the server (badge shows Reconnecting, server exits in 5 s) and restarting it (reconnects by itself), phone width and dark mode, and no console errors other than the deliberate outages. Temperatures only verified with fakes (macOS has no sensors API).

- **M4 step 2, dashboard apps** (#21):
  - `AppOut` now carries `title` and `icon` from the app's catalog entry (`None` for compose apps or if the catalog was removed).
  - Web: an Apps card on the dashboard (tiles with icon, status, Open, start/stop; Store and All apps links; the runtime Start/setup panel when containers aren't ready). `useAppsList()` is shared with the Apps page, which now shows icons too. After any tile action the list reloads at once, so a failed action doesn't leave a stale tile.
  - 179 server tests. Verified in the browser on Colima with a store Forgejo and a compose nginx app (both `athena-test-*`): icons and fallback initials, Open links (:3012, :18090), stop and start from the tiles (checked with `docker ps` and curl), stopping an app removed behind the UI's back (error toast, tile gone in ~200 ms), the stopped-runtime panel (fake empty `HOME`), phone width and dark mode. Test apps removed afterwards.

- **M4 step 3, Settings** (#22):
  - `scripts/gen-theme-css.mjs` (`pnpm gen:theme`) generates `packages/ui/src/styles/themes.css` and `themes.json` from the shadcn registry (7 bases, 24 themes, 23 chart palettes, 5 radii, 26 fonts) and checks 18 combinations against it. `gray` is skipped (the registry refuses it).
  - All preset fonts via `next/font` (`apps/web/lib/fonts.ts`); `font-heading` and `font-mono` now read runtime variables in `globals.css`.
  - `users.appearance` (migration 0006), `GET/PUT /api/settings/appearance`, `POST /api/auth/password` (keeps this session, signs out others, throttled, audited).
  - Web: pre-paint inline script, `AppearanceProvider` (account settings win, instant apply, 400 ms debounced save, follows the `d` hotkey), Settings → Appearance (mode, base, theme, charts, fonts with previews, radius, read-only style, preset code copy/apply) and Settings → Account (change password); Settings in the sidebar.
  - 189 server tests (10 new). Verified in the browser: every setting applies live and is saved; the UI's code for stone/blue/emerald/Geist/Lora/large is `b4DwxjALIm`, exactly what shadcn's encoder gives; settings come back from the account after clearing local storage; attributes are on `<html>` before `<body>` parses; preset import (invalid code → inline error; unsupported parts → warning toast); rose's dark sidebar; wrong current password (inline error, still signed in); password change (other session 401, old password rejected, audit row); phone width; dark mode.
  - Found and fixed during verification: the provider's initial load re-ran whenever next-themes changed `setTheme`'s identity, which re-applied the old saved settings and cancelled the pending save, so quick changes after an import were lost. It now loads once and builds each change on the latest state.

- **M5 part A, package managers** (branch `feat/m5-packages`):
  - `athena/packages/`: apt, dnf (4 and 5), zypper, pacman, apk, Homebrew, Flatpak, Snap, winget, Scoop, Chocolatey. Search, installed, upgradable; install, uninstall, upgrade (one or all), refresh lists, as jobs, one per manager at a time, audited.
  - `/api/packages` (managers from the capability manifest, including `needs_privilege` ones with the reason), `/{mgr}/search|installed|upgradable`, `/{mgr}/install|uninstall|upgrade|refresh`.
  - Fixtures: real recordings for brew, apt, apk, dnf4/dnf5, zypper, pacman and flatpak search (throwaway containers, images removed afterwards) and winget list (Windows CI runner); hand-written for snap, scoop, choco and the rest of winget (README says which). CI's real reads: apt (Ubuntu), brew (macOS), choco and winget (Windows) all parse; the first Windows run showed winget ids can contain spaces, now handled. Read-only real-tool tests run where the tool exists (brew passes locally).
  - Web: Packages page (tab per manager; Installed with filter, inline update badges, uninstall; Updates with upgrade one/all; Search with install), confirm dialogs, job dialog, notes (pacman, choco). Nav item via `capability: "packages.*"`.
  - 238 server tests pass (49 new); the real-tool tests for apt, choco and winget skip on this Mac and run in CI on their OS. Verified in the browser on macOS with real Homebrew reads and a stub for changes (nothing installed or removed on the host): installed list (49) and updates (12) match `brew`, filter, search with descriptions, install (stub), a failing install (exit code and Homebrew's error in the dialog), upgrade all and uninstall with confirmations (cancel sends nothing), refresh, audit rows, phone width (fixed: row actions were pushed off-screen), dark mode, no console errors; a host without Homebrew hides the nav item and the page says so.

## In progress

- M5 part A (packages) review and merge.
- Not yet verified for real: the Linux system managers' install/uninstall (only recorded reads and fakes) and every Windows manager (hand-written fixtures; CI runs choco/winget reads on Windows).
- Not yet verified: a real `athena service install` on any OS (only dry runs), and real capability detection on Linux and Windows hosts (only CI and fakes).

## Next

M5 part B, terminal (see `docs/mvp-design.md` §4.2, §7): host shell in the browser (xterm.js over a WebSocket; a pty on Linux/macOS, ConPTY on Windows) and container exec; admin-only, can be switched off, audited.

Later: a CI check that `themes.css` matches the registry (needs network; run `pnpm gen:theme` after shadcn upgrades for now), and switching shadcn styles at runtime (§5.4).

Later: auto-refreshing catalogs on a schedule, stripping missing host devices from imported apps, and Docker Hub login for pulls (rate limits).

Later: per-container stats, verifying temperatures on a real Linux host, importing existing compose projects not created by Athena, and Windows path translation for WSL bind mounts.

## Open questions

- Should the first-run wizard suggest a cloud AI provider or local Ollama first? (`docs/mvp-design.md` §12)

## Blockers

- The release PR needs a `RELEASE_PLEASE_TOKEN` repo secret (a fine-grained PAT with contents + pull-requests write on this repo). Without it, CI doesn't run on release-please PRs, and they can only be merged with admin bypass.
