# Athena

**A self-hosted home server dashboard for Linux, macOS and Windows.**

Athena manages containers, apps, host packages, files and cloud storage from one web dashboard, and includes an AI assistant that can operate it all. It's in the spirit of [CasaOS](https://github.com/IceWhaleTech/CasaOS), but cross-platform: it detects what your machine has and only shows what works there.

> **Status: pre-alpha.** The design is done and the first milestone is in progress. Nothing is installable yet. See [docs/STATUS.md](docs/STATUS.md).

## Planned features (MVP)

- **Apps**: an app store plus custom apps from `docker run` commands or `compose.yaml`. Uses Docker Engine on Linux, [Colima](https://github.com/abiosoft/colima) on macOS, and Docker Engine in WSL2 or Podman on Windows.
- **Packages**: install and update host software with apt, dnf, pacman, zypper, apk, flatpak, snap, Homebrew, winget, Scoop or Chocolatey, whichever your system has.
- **Dashboard**: live CPU, memory, disk and network stats, plus app status.
- **Terminal**: a web terminal for the host and for containers.
- **Files and sharing**: a file manager, share links and WebDAV shares.
- **Cloud storage**: Google Drive, OneDrive, Dropbox, S3 and more through [rclone](https://rclone.org).
- **AI assistant**: built on [Pydantic AI](https://ai.pydantic.dev). It works with cloud models or local Ollama, and asks for your approval before changing anything.
- **Appearance**: switch base color, theme, chart colors, fonts and radius live.

Athena uses open-source dependencies only. See the full design in [docs/mvp-design.md](docs/mvp-design.md).

## Install (once the first release is out)

**Linux / macOS**

```bash
curl -fsSL https://github.com/tiagozaccaro/athena/releases/latest/download/install.sh | bash
```

**Windows** (PowerShell)

```powershell
irm https://github.com/tiagozaccaro/athena/releases/latest/download/install.ps1 | iex
```

Then open `http://<your-server-ip>:8420`. The first visit asks you to create the administrator account. Run the script with `--help` (or `-Help` on Windows) to see options such as a specific version, a dry run, or uninstall.

**Forgot the admin password?** Run this on the server (with `sudo` on Linux), then sign in with the new password. All existing sessions are signed out.

```bash
athena admin reset-password
```

## Development

The project is a monorepo: a Next.js + shadcn/ui frontend (pnpm + Turborepo) and a Python backend (uv).

**Requirements:** Node.js 20.9+, [pnpm](https://pnpm.io), and [uv](https://docs.astral.sh/uv/).

```bash
pnpm install
cd apps/server && uv sync && cd ../..
```

Run the backend and the frontend in two terminals:

```bash
cd apps/server && uv run athena serve --reload --port 8420
```

```bash
pnpm dev
```

Open http://localhost:3000. `next dev` proxies `/api` to the server on port 8420, and the API docs are at http://localhost:8420/api/docs.

| Task | Command |
|---|---|
| Lint, typecheck, build the web app | `pnpm lint`, `pnpm typecheck`, `pnpm build` |
| Server tests and lint | `cd apps/server && uv run pytest && uv run ruff check` |
| Regenerate the API client after changing server routes | `pnpm gen:api` |
| Add a shadcn component | `pnpm dlx shadcn@latest add <name> -c apps/web` |

| Path | What |
|---|---|
| `apps/web` | Next.js app (static export), app shell from the shadcn `dashboard-01` block |
| `packages/ui` | shadcn/ui components shared by the app |
| `packages/api-client` | Typed API client generated from the server's OpenAPI schema |
| `apps/server` | FastAPI server and the `athena` CLI (`serve`, `openapi`, `service install`) |

More reading:

- [docs/mvp-design.md](docs/mvp-design.md): architecture and decisions
- [CONTRIBUTING.md](CONTRIBUTING.md): branches, commits and pull requests
- [AGENTS.md](AGENTS.md): instructions for AI coding agents (Claude Code, OpenCode, Hermes Agent)

## Security

Please report vulnerabilities privately. See [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)
