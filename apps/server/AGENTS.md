# Athena server (`apps/server`)

Rules for working on the Python server. The repo-wide rules, Git workflow and handoff are in the root `AGENTS.md`; read that first. Lessons and gotchas are in `docs/AGENT-NOTES.md`. For step-by-step changes (endpoint, migration, job, setting), use the `athena-recipes` skill. For anything that touches the host OS, use `athena-platform-feature`.

## Stack and commands

Python 3.13 (uv), FastAPI, SQLModel and Alembic on SQLite. Package `athena`, CLI `athena` (`serve`, `openapi`, `service install|uninstall|status`). Run everything with `uv run` from this folder:

| Task | Command |
|---|---|
| Tests | `uv run pytest -q` (`-k name` to narrow) |
| Lint and format | `uv run ruff check` and `uv run ruff format --check` (CI runs both) |
| Real-engine tests | `ATHENA_DOCKER_TESTS=1 uv run pytest -q`. They touch your container engine, so they're opt-in (on in Linux CI) |
| Run the server | `uv run athena serve --port 8421 --data-dir "$DATA"` (8420 may be the developer's own Athena) |
| After any API change | `pnpm gen:api` from the repo root; CI fails if `packages/api-client` is stale |
| Everything CI checks | `scripts/check.sh server` from the repo root |

## Module map (`src/athena/`)

| Module | What it holds |
|---|---|
| `main.py` | `create_app()`: wiring, `app.state`, every `include_router` |
| `cli.py`, `config.py` | The CLI and settings (data dir via platformdirs, `ATHENA_*` env) |
| `api/` | One thin router per area. Logic lives in the area packages below |
| `auth/` | Sessions, argon2id passwords, CSRF (`deps.py`: `require_user`, `Authed`, `DbSession`) |
| `db/` | `models.py` (SQLModel), `engine.py`, `db/migrations/versions/` (Alembic) |
| `platform/` | Host detection: `probe.py` (never raises), `detect.py`, `capabilities.py`, `store.py` |
| `containers/` | `runtime.py` (`runtime_from(capability)` gives the CLI prefix and client), `service.py` (operations, `check_ref`) |
| `apps/` | `store.py` (on-disk layout, compose checks, `store.compose(...)`), `docker_run.py` (converter) |
| `catalog/` | `model.py` (`x-athena` format), `loader.py` (load and resolve install values), `registry.py` (built-in plus downloaded catalogs), `remote.py` (fetch and extract archives), `casaos.py` (CasaOS import) |
| `packages/` | `base.py`, then one class per manager in `linux.py`, `apps.py` (brew, flatpak, snap), `windows.py`; `MANAGERS` in `__init__.py` |
| `files/` | `paths.py` (containment), `locations.py`, `ops.py`, `shares.py`, `webdav.py` |
| `cloud/` | `rclone.py` (the `rclone rcd` sidecar and its client), `remotes.py` (backends, remotes, config questions, remote paths), `transfers.py` (copy, move and sync jobs with progress and cancel) |
| `terminal/` | `pty.py` (one async pty for POSIX and ConPTY), `shells.py` (host or container shell) |
| `service/` | `athena service install` per OS (`platforms.py`, `plan.py`) |
| `jobs.py`, `audit.py`, `monitor.py`, `system_settings.py` | Jobs over SSE, the audit log, host stats, host-wide settings |

## Conventions

- **Routes:** everything is under `/api`, and each route has an explicit camelCase `operation_id`. New routers must require a session: `include_router(..., dependencies=[require_user])`, which also CSRF-checks writes. The only public routes are health, `/api/auth/*` and a share link's `/api/public/shares/{token}`. WebDAV at `/dav/` has its own sign-in, and the terminal WebSocket checks its session and CSRF itself (see the top of `api/terminal.py`).
- **Database:** every model change needs a new migration in `db/migrations/versions/`. `tests/test_db.py` fails if the models and migrations differ. Migrations run on every start.
- **Long operations** run as jobs: `request.app.state.jobs.start(title, body)`, with `run_or_fail(job, argv, what, env=...)` inside, returning 202. One job per resource at a time.
- **Audit** privileged actions with `athena.audit.record(db, username, "<area>.<action>", target)`.
- **Commands:** use argument lists, never `shell=True`. Validate user-supplied names before they reach a CLI (`check_ref`, `PACKAGE_NAME`), and reject a leading `-`. Run with `LC_ALL=C.UTF-8` when parsing output.
- **Apps:** compose commands go through `store.compose(...)` with `env=store.env(name)`, so `${ATHENA_APP_DATA}` resolves. That applies to stop, restart and remove, not just deploy. Installs go through `deploy_new_app()` in `api/apps.py`.
- **Catalog:** apps live in `catalog/apps/<id>/compose.yaml` at the repo root (see `catalog/README.md` and the `athena-catalog-app` skill). `tests/test_catalog.py` checks every one. Remote fetches are stubbed in tests (`remote.download`).
- **Packages:** parsers are pure functions over recorded output. A new parser needs a fixture in `tests/fixtures/packages/` and a line in that folder's README saying how it was captured.
- **Shares and WebDAV:** `api/shares.py` has the admin `router` plus the public `public_router`. `files/webdav.py` holds the wsgidav provider, sign-in and the `/dav` middleware. Location folders can never be deleted, moved or replaced over WebDAV (wsgidav would empty them).
- **Cloud (rclone):** talk to rclone only through `app.state.rclone` (`Rclone.call`), never by running the `rclone` CLI. Check remote paths with `remotes.check_path` and build fs strings with `remotes.fs_of`. rclone itself lets `name:..` leave an alias's folder. Jobs that run rclone transfers use `transfers.run(job, rclone, steps)` and start with `cancellable=True`.
- **Host access** always goes through a capability; never branch on `sys.platform` in a router. See the `athena-platform-feature` skill.

## Tests

- **Apps for tests:** `conftest.make_app(tmp_path)` builds an app on a fake macOS host. Pass `store=` with a `FakeProbe` from `tests/fake_probe.py` to simulate another OS. `signed_in(client)` creates the admin and sets the CSRF header.
- **Tests that start jobs** must hold the `TestClient` open as a context manager for the whole test (see `client_for` in `tests/test_packages_api.py`), or the job's event loop closes.
- **Real-tool tests** use `pytest.mark.skipif` when the tool or engine is missing, so each CI OS runs its own (apt on Ubuntu, brew on macOS, winget and choco on Windows).
- **Cloud tests** (`tests/test_cloud.py`) run a real `rclone rcd` (CI installs rclone on all three OSes) with `alias` remotes over temporary folders, plus a `FakeRclone` for things rclone can't easily produce, like a transfer that's still running when it's cancelled.
- **Write code that passes on Windows:**
  - Open text with `encoding="utf-8"`, and write fixtures with `write_bytes`.
  - Compare `Path` objects, not strings with `/`.
  - Paths written into Linux or macOS files stay forward-slash.

  More in `docs/AGENT-NOTES.md` → Windows portability.
