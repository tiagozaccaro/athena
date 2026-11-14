# Agent notes

_Shared knowledge for every coding agent on Athena (Claude Code, OpenCode, Hermes Agent, others)._

This file holds the lessons from earlier sessions: how the maintainer works, the commands that matter, the patterns to copy, and the traps that have already cost someone time. It complements the other docs:

- `AGENTS.md`: the rules.
- `docs/STATUS.md`: where the work is now.
- `docs/mvp-design.md`: the design and the decisions.

Read this file once per session, after STATUS.

**Keep it alive.** When you learn something non-obvious that the next agent would otherwise rediscover, add it in the right section. Examples: a CI failure with a surprising cause, a tool quirk, a false positive, a pattern that worked. Use one bullet per fact and say _why_. Delete bullets that stop being true. Design decisions still go in `docs/mvp-design.md` §11, not here.

## Working with the maintainer

- They move through the milestones in `docs/mvp-design.md` §10 in order, with short prompts like "next", "continue", "start M5", "check" or "yes". "Next" means: read STATUS, propose the next concrete step with a recommendation, and wait for a yes before starting a new milestone or part.
- Big milestones are split into parts (M5 A/B, M6 A/B/C), with one branch and one PR per part.
- When asked to "discuss questions first", list the open questions with a recommendation for each before writing code.
- After opening a PR, they usually say "Yes, auto-merge". Turn it on with `gh pr merge <n> --squash --auto --delete-branch`. Auto-merge only waits for the required checks (`ci-ok`, `pr-title`), so also check that CodeQL is green before you call a PR done.
- "Check" / "check now" / "could you keep observing the PRs?" means: read the PR checks (`gh pr checks <n>`, `gh run view <id> --log-failed`), fix failures on the PR branch, and report what merged and what didn't. Never claim something merged without checking.
- Fix CodeQL alerts in code rather than dismissing them. Dismissing changes the repo's security state, so it's the maintainer's call (see [CodeQL](#codeql)).
- Report honestly: what was verified, what wasn't and why, and the bugs found along the way. Final reports list "Fixed along the way" and "Not tested yet".
- They can't see your private memory. Anything another agent needs goes in the repo.

## Command cheat sheet

Run pnpm from the repo root and Python with `uv run` inside `apps/server`.

| Task | Command |
|---|---|
| All web checks | `pnpm lint && pnpm typecheck && pnpm build` |
| Server lint | `cd apps/server && uv run ruff check . && uv run ruff format --check .` |
| Server tests | `cd apps/server && uv run pytest -q` (add `-k name` to narrow) |
| Real-engine tests | `ATHENA_DOCKER_TESTS=1 uv run pytest -q -k docker` (touches your engine; opt-in) |
| Regenerate API client | `pnpm gen:api` (after any API change; CI fails on drift) |
| Regenerate theme CSS | `pnpm gen:theme` (after shadcn upgrades; needs network) |
| Agent config sync | `node scripts/agents-sync.mjs` (after editing `.mcp.json`); `--check` is what CI runs |
| Release server for UI checks | `pnpm build` then `cd apps/server && ATHENA_WEB_DIR=../web/out uv run athena serve --port 8421 --data-dir "$DATA"` |
| Dev mode | `pnpm dev` (Next on :3000, proxies `/api` to :8420) plus `uv run athena serve` |
| Build the wheel | `scripts/build-wheel.sh` (also used by `release.yml` and the E2E workflow) |
| Installer dry run | `scripts/install.sh --dry-run`; `athena service install --dry-run` |
| PR status | `gh pr checks <n>`, `gh run view <run-id> --log-failed`, `gh api repos/tiagozaccaro/athena/code-scanning/alerts?state=open` |

CI jobs (`.github/workflows/ci.yml`):

- `repo checks`: agent config sync, the `.claude/skills` symlink, actionlint, shellcheck.
- `install script` on 3 OSes: dry runs plus PSScriptAnalyzer.
- `web`: API client drift, lint, typecheck, build.
- `server` on 3 OSes: ruff, pytest, service dry run.
- `ci-ok`: the single required check.

Other workflows: `pr-title`, CodeQL (separate; it can block merges), and `E2E` (`e2e.yml`). E2E is slow and not part of `ci-ok`. It runs on pushes to main, on installer or service changes, and on demand.

## Patterns to copy

When adding something, start from the closest existing feature instead of inventing a new shape.

- **Host feature end to end:** follow the `athena-platform-feature` skill. Packages (`athena/packages/`, `api/packages.py`, `components/packages/`) is the cleanest full example: a capability per manager, pure parsers, jobs, audit, UI gated by `capability: "packages.*"`.
- **Long operation:** `request.app.state.jobs.start(title, body)`, with `run_or_fail(job, argv, title, env=...)` from `athena/jobs.py` inside. Return the job id with 202. The UI opens `<JobDialog job>`. Allow one job per resource at a time (see `app.state.package_jobs`).
- **Audit:** `athena.audit.record(db, username, "<area>.<action>", target)`, e.g. `package.install` with `apt:jq`.
- **Command execution:** use argument lists, never a shell. Set `LC_ALL=C.UTF-8` for parseable output. Validate user-supplied names with a regex that rejects a leading `-`, so a value can't become a flag: `PACKAGE_NAME` in `packages/base.py`, `check_ref` in `containers/service.py`.
- **Parsers:** pure functions over recorded output in `tests/fixtures/<area>/`, each recorded in a throwaway container where possible, with a README line saying how. Real-tool read-only tests use `pytest.mark.skipif` when the tool is missing, so Ubuntu CI runs apt, macOS runs brew and Windows runs winget/choco. Those real runs found bugs the hand-written fixtures missed.
- **API tests:** use `conftest.make_app()` and `signed_in(client)`. Tests that start jobs must enter the `TestClient` as a context manager (see `client_for` in `test_packages_api.py` and `test_terminal.py`). Otherwise jobs die with "event loop is closed".
- **Settings:** per-user settings go in `users.appearance` (`api/settings.py`). Host-wide switches go in the `system_settings` JSON row (`athena/system_settings.py`), and only admins can change them.
- **Missing capability in the UI:** render shadcn `Empty` with the capability's `detail` and its setup/start action, never a broken page. Containers pages wrap in `<RequireContainers>`.

## Gotchas

### Git, GitHub and CI

- Force pushes are blocked, so don't rebase a pushed branch. To bring in `main`, merge it into the branch; the squash merge hides the merge commit.
- When a PR stacked on another PR's branch has its base merged, GitHub retargets it to `main`. Merging `main` in then shows conflicts that are only squash artifacts. Resolve them toward `main`'s content.
- Don't turn on auto-merge for a PR whose base is another feature branch. That branch isn't protected, so it merges immediately into the wrong base.
- Two open PRs that both edit `docs/STATUS.md` or `AGENTS.md` will conflict. The second one needs its branch updated and the docs merged by hand; auto-merge won't do it.
- Never commit conflict markers into a generated file. For `packages/api-client/openapi.json` (or the generated types), resolve a conflict by rerunning `pnpm gen:api`, not by editing. Once, markers were committed and `web` failed.
- A macOS runner can sit queued for a long time and then be _cancelled_, which fails `ci-ok` with no code problem. Re-run the failed jobs.
- Dependabot can't fix a transitive pnpm dependency. Add an override in `pnpm-workspace.yaml` with a comment saying why (see the existing `baseline-browser-mapping`, `brace-expansion` and `minimatch` overrides), and remove it once upstream ships a fix.
- `pr-title` accepts Dependabot's capitalized "Bump …" subject; only the Conventional Commit type is enforced.
- release-please PRs need the `RELEASE_PLEASE_TOKEN` secret to run CI (see STATUS → Blockers). Don't merge a release PR yourself.
- The first release is 0.1.0 because of explicit config. release-please defaults to 1.0.0 without it.

### Windows portability (CI catches these; your Mac won't)

- Paths written into Linux/macOS files (systemd units, launchd plists, Colima socket paths) must use forward slashes even when generated or tested on Windows. Use `PurePosixPath` or string paths, not `Path`.
- Tests that compare paths must not hard-code `/`. Compare `Path` objects.
- Open text files with `encoding="utf-8"`. Windows defaults to cp1252, which gave a `UnicodeDecodeError` in catalog tests.
- Write test fixtures as bytes (`write_bytes`). Text mode on Windows turns `\n` into `\r\n` and breaks content checks.
- Windows silently strips trailing dots and spaces from names, so `...` resolves to the parent folder. Path containment must check that the final name is unchanged, not only that the parent is inside the root (see `athena/files/paths.py` and design §4.3). This was a real "delete the whole location" bug.
- winget IDs can contain spaces (`ARP\Machine\X64\Mozilla Firefox`), and its truncation ellipsis arrives as `�`.
- Recorded fixtures are stored byte-exact (`apps/server/tests/fixtures/** -text` in `.gitattributes`), so CRLF and spinner `\r` survive.
- In `install.ps1`, a failed native command (e.g. `wsl.exe` with no distro) leaves `$LASTEXITCODE` set, and CI reads the script as failed. Reset it after expected failures.
- PSScriptAnalyzer's unused-parameter rule only looks at the script's top level, so it flags parameters used inside functions (`-Wheel`). Suppress that rule for that parameter with a reason.
- On Windows, `schtasks /End` only kills the venv's `pythonw.exe` launcher. The real interpreter keeps the port and locks the install folder. The installers also stop `pythonw.exe -m athena serve` processes and wait for them.
- PowerShell isn't installed on the maintainer's Mac. The CI run is the first real check of `.ps1` changes.

### CodeQL

CodeQL runs on every PR and its alerts can block a merge.

- Any identifier containing "password" is treated as a secret. A constant named `MIN_PASSWORD_LENGTH` was flagged as "clear-text logging of password"; it's now `MIN_PW_LENGTH`.
- A fast hash (SHA-256) over anything derived from a password is flagged as weak password hashing, even as an in-memory cache key. Don't hash passwords for keys or caches; compare against what argon2 already produced.
- `hmac.compare_digest` on `str` raises on non-ASCII. Compare bytes.
- Regexes over URLs get flagged (ReDoS / incomplete sanitization). Prefer `urllib.parse` plus plain string checks.
- In the web app, sending server text to something named `write` looks like `document.write` (client XSS). The terminal wrapper's method is called `output` for that reason. Strip control characters from server-provided strings shown in the terminal, and accept only integers for exit codes.
- Path-injection alerts on file APIs are usually real. See the Windows trailing-dot bug above.

### Server (Python)

- `athena openapi` must not create the real data dir. It builds the app against a temp dir, and a test enforces this.
- SQLite runs in WAL mode. A test that reads `athena.db` directly misses rows still in `athena.db-wal`, so query through SQLAlchemy.
- `ruff --fix` can delete an import it thinks is unused when the name is shadowed. Use an aliased import.
- Mutable class attributes trip RUF012. Use tuples or `ClassVar`.
- The capability status type is `Status` (`athena/platform/`), not `CapabilityStatus`.
- Open SSE streams never end on their own. uvicorn's `timeout_graceful_shutdown` (5 s, `SHUTDOWN_GRACE_SECONDS` in `cli.py`) is what lets the service stop with a dashboard open. Keep it.
- Every compose command needs `env=store.env(name)`, not only deploy. Stop, restart and remove once failed for apps using `${ATHENA_APP_DATA}`.
- Compose YAML is YAML 1.2: `yes` is a string, not `true`. The CasaOS importer parses it the same way (one of 182 apps broke on this).
- Terminal: don't use `pty.fork()` or ptyprocess in the multi-threaded server; they can deadlock (Python 3.12+ warns). Use the stdlib pty with `Popen(start_new_session=True)` and the `TIOCSCTTY` shim in `athena/terminal/pty.py`.
- `require_user` can't protect WebSockets. The terminal checks the cookie itself and takes the CSRF token in the first message (see the top of `api/terminal.py`).
- wsgidav: a DELETE on a collection whose `delete()` refuses falls back to deleting every member one by one. That emptied a whole location. Refuse such requests in `handle_delete` / `handle_copy` / `handle_move` before wsgidav gets there, and test it.
- Tests that need a CLI to be _absent_ must really hide it from PATH. A test passed on every machine with `docker` and only failed on macOS CI, which has none. Run such tests with the tool removed from PATH.
- The release wheel must include the catalog (`athena/catalog_builtin`) and the web export. Once it shipped without the catalog, and the store was empty. `build-wheel.sh` now fails if either is missing.

### Web (Next.js 16, shadcn on Base UI)

- Base UI, not Radix: component APIs differ (`render` prop instead of `asChild`, different `Select` and `ToggleGroup` APIs). Check the `shadcn` skill or `shadcn docs <component>` before using one.
- The shadcn CLI may drop files in `apps/web` that belong in `packages/ui`. It put `use-mobile` in `apps/web/hooks` while the sidebar imported it from `packages/ui`, which broke typecheck. Check where added files land.
- `trailingSlash: true` (needed so FastAPI's `StaticFiles` serves `<route>/index.html`) made `next dev` 308-redirect every `/api` call before proxying it. The dev config sets `skipTrailingSlashRedirect: true`; keep it when touching `next.config.ts`.
- `next-env.d.ts` is gitignored, and CI typechecks before building. Don't rely on it existing.
- next/font: each loader call must be its own module-level `const` with literal options. Spreads or calls inside an object literal fail the build (`apps/web/lib/fonts.ts`).
- Appearance is applied before paint by `APPEARANCE_SCRIPT` in `<head>`, and re-applied in `useLayoutEffect` after the dev Strict Mode remount. next-themes changes `setTheme`'s identity on mode change; an effect depending on it re-ran the initial load and undid the user's change. Use refs and a load-once effect.
- Theme generation (`scripts/gen-theme-css.mjs`): themes depend on the base color, `chartColor` must be omitted for neutral, `rose` changes the dark sidebar (so keys are tracked per mode), and the registry refuses `gray`, so it's skipped.
- Toasts must sit above sheets and dialogs. Both were `z-50`, which hid every error toast behind side panels. The toast viewport is raised in `packages/ui/src/components/toast.tsx`; don't lower it.
- Generated types sometimes lack a shape you need (e.g. `HostStats`). Derive it (`Omit<StatsSnapshot, "history">`) rather than hand-writing request types.
- Byte formatting: values just under a unit boundary must switch unit (no "1024 B/s").
- After any action that changes a list (apps, files), reload the list. A stale tile after a failed action was a real bug.
- Links rendered from untrusted text (terminal output) must allow only `http(s)` and open in a new tab. A `javascript:` link was clickable once.
- Next 16 proxying of the terminal WebSocket in `next dev` is unchecked. Use the release build for terminal work.

### Browser verification (`athena-ui-verify`)

- Base UI checkboxes and switches render a hidden `<input>`. A click on it "works" but sends the wrong value, and only `browser_network_requests` showed that. Click the visible control and re-snapshot.
- Take a fresh snapshot after a dialog closes or the layout shifts. Stale refs click the wrong thing, and clicking while a page is still loading misses.
- A rebuilt web export is served without restarting the server. Server or catalog changes need a restart.
- Fake anything that would change the host: a stub `brew`/`colima` first on the server's `PATH` (reads can pass through to the real tool), or `HOME` pointed at an empty folder so a runtime looks stopped. For files, point `HOME` at a scratch folder so the default Home location isn't the real one.
- Anonymous Docker Hub pulls are rate-limited (429). Image-checking loops used up the quota for hours. Prefer ghcr.io or codeberg.org images in tests, and don't loop `docker manifest inspect`.
- Keep the developer's personal data out of fixtures and screenshots. For example, a fixture once used a real installed-cask list and was replaced with neutral entries.
- What the sandbox can't do: `mount_webdav` (Finder mounts), `.claude/settings.json` edits, and turning on Claude's PR monitor. Say so and leave them to the maintainer; don't work around the guard.

### Installers and E2E

- Hosted runners can't run Colima's VM (macOS) or WSL2 (Windows), so containers are only checked end to end on Linux in CI.
- For a full Linux check locally on a Mac, use a Lima VM (`limactl start template://ubuntu`, or `template://fedora` for dnf). Docker containers don't run systemd, so they can't test the service.
- Installers take `--wheel <path>` / `-Wheel <path>` so E2E tests the commit, not the last release.
- Recording pacman fixtures under amd64 emulation on Apple Silicon needs `--disable-sandbox` (for recording only).

### Agent environment

- The maintainer's shell is zsh. `echo =====` fails there (`=word` expands to a command path), and unquoted `$VAR` lists don't word-split. Quote or use arrays.
- Claude Code's safety check refuses `rm` with unguarded variables or globs (`rm -rf $S/*`). Use literal paths.
- Hermes quarantines `pydantic-ai-harness` as "dangerous" (a false positive). Read its `SKILL.md` directly.
- Another agent session may be working in the main checkout at the same time (uncommitted changes on its feature branch). For unrelated work, use `git worktree add ../athena-<topic> -b <branch> origin/main` instead of switching branches under it.
- Port 8420 may be the maintainer's own Athena. Use 8421 or another spare port.
- Act only on containers, apps and images named `athena-demo-*` / `athena-test-*`. The maintainer's own containers run on the same engine. Leave pulled images unless you know you pulled them, and say which ones are left.
