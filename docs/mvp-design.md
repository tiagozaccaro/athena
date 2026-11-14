# Athena — MVP Design

Athena is a self-hosted home server control panel in the spirit of CasaOS, that runs on **Linux, macOS and Windows**. It manages containers (Docker/Compose), host package managers, files, shares and cloud storage, and includes an AI assistant that can drive all of it.

Hard rules that shape every decision below:

1. **Cross-platform.** Every feature goes through a platform provider. Nothing in the API or UI assumes Linux.
2. **Show only what exists.** The backend detects what the host has and publishes a *capability manifest*. The UI renders navigation, pages and actions from that manifest. If `apt` isn't on the box, the user never sees an apt option.
3. **Open-source dependencies only.** No Docker Desktop, no macFUSE, no proprietary SDKs. Licenses are listed in [§9](#9-dependency--license-inventory).

---

## 1. MVP scope

| Area | In the MVP | Later |
|---|---|---|
| Dashboard | Host stats (CPU, RAM, disk, network, uptime), running apps grid, runtime status | Custom widget layout, multi-node |
| Container runtime | Detect, report status, start the runtime (Colima on macOS), guided setup when missing | One-click runtime install on every OS |
| Apps (containers) | List, start/stop/restart, logs, stats, remove, update image | Backups, auto-update policy |
| App store | Built-in catalog plus remote catalogs (Git/HTTP), install with editable env/ports/volumes | Ratings, signed catalogs |
| Custom apps | Import a `docker run` command, paste/upload a `compose.yaml`, edit before deploy | Import from a Git repo |
| Package managers | Search, install, uninstall, list installed, upgrade, for each detected manager | Scheduled upgrades |
| Terminal | Web terminal to the host shell (bash/zsh/PowerShell) and `exec` into containers | Session sharing, recordings |
| Files | Browse, upload, download, rename, move, delete, preview text and images | Thumbnails, search index |
| File sharing | Public/expiring share links, WebDAV share of chosen folders | SMB/NFS where the OS supports it |
| Cloud storage | Add remotes via rclone (Google Drive, OneDrive, Dropbox, S3, WebDAV…), browse, copy/sync jobs | Mounts as local drives, scheduled sync |
| AI assistant | Chat that can query state and do actions through Athena's own services, with approval for destructive actions | Proactive alerts, runbooks, MCP servers |
| Settings | Appearance (style, base color, theme, chart color, heading font, body font, radius), users, AI provider, catalogs | RBAC, SSO |
| Auth | Single admin account, created in a first-run wizard | Multiple users with roles |

---

## 2. Architecture

```
┌──────────────────────────── Browser ────────────────────────────┐
│  Next.js (static export) + shadcn/ui   ·   xterm.js   ·  AI chat │
└───────────────▲──────────── REST / SSE / WebSocket ─────────────┘
                │
┌───────────────┴─────────── athena-server (Python, uv) ───────────┐
│ FastAPI routers  →  services  →  providers (per-OS adapters)     │
│                                                                 │
│  platform/detect ─► CapabilityManifest                          │
│  providers/containers   docker-engine · colima · podman · wsl    │
│  providers/packages     apt dnf pacman zypper apk brew           │
│                         winget scoop choco flatpak snap          │
│  terminal               stdlib pty (POSIX) · pywinpty (Windows)  │
│  providers/storage      rclone rcd (sidecar process)             │
│  assistant/             pydantic-ai Agent + harness capabilities │
│  SQLite (settings, users, installed apps, jobs, shares)          │
└─────────────────────────────────────────────────────────────────┘
        │ Docker API socket       │ CLI subprocess       │ HTTP
   Docker Engine / Colima /   package managers       rclone rcd
   Podman (docker-compat)
```

### Decisions

- **One backend process serves everything.** Next.js is built with `output: "export"` and the static files are served by FastAPI. Users don't need Node.js on their server and packaging stays simple. The trade-off is no SSR or server actions; every page is a client component that calls the API. That's acceptable for a LAN dashboard.
- **Typed contract.** FastAPI generates OpenAPI. `openapi-typescript` and `openapi-fetch` generate the TS client in `packages/api-client`, so the frontend never hand-writes request types.
- **Realtime.** Server-Sent Events carry stats, logs, job progress and the AI chat stream. WebSockets are used only where input is two-way, which means the terminal.
- **Long operations are jobs.** Image pulls, package installs and rclone syncs return a `job_id` right away and stream progress over SSE. A small in-process job runner backed by SQLite is enough. No Celery or Redis.
- **Talk to container engines through a Docker-compatible CLI** (`docker --host <endpoint>`, `podman --url <endpoint>`, or `wsl.exe -e docker`), using `python-on-whales` for structured reads and direct subprocesses for streamed operations (logs, compose up, pulls). Revised in M2 from "Docker API via the docker SDK": Docker inside WSL2 has no socket reachable from Windows, and the CLI is the one path that covers it, Docker Engine, Colima, Podman and Rancher Desktop alike. Detection still pings the Docker API socket directly (no CLI needed for that).

---

## 3. Platform layer and capability manifest

This is the core of the cross-platform requirement.

```python
# athena/platform/capabilities.py
class Capability(BaseModel):
    id: str                 # "containers", "packages.apt", "terminal.host", "shares.webdav"
    available: bool
    status: Literal["ready", "stopped", "missing", "unsupported", "needs_privilege"]
    provider: str | None    # "colima", "docker-engine", "winget"…
    detail: str | None      # human-readable reason / version
    actions: list[str]      # e.g. ["start", "setup"] for a stopped/missing runtime

class CapabilityManifest(BaseModel):
    os: Literal["linux", "darwin", "windows"]
    distro: str | None      # "ubuntu 24.04", "macOS 26", "Windows 11 24H2"
    arch: str
    capabilities: list[Capability]
```

- Detection runs at startup and on demand (`POST /api/system/capabilities/refresh`). It probes binaries (`shutil.which`), sockets and versions.
- `GET /api/system/capabilities` drives the UI. The sidebar, the package-manager tabs, the "Open terminal" buttons and the AI assistant's toolset are all filtered by it.
- **The AI agent gets the same filter.** Its tools are registered from the manifest, so it can't call `apt` on macOS.

### Container runtime per OS

| OS | Default | Alternatives detected | Notes |
|---|---|---|---|
| Linux | Docker Engine (Moby, `docker-ce`) | Podman (rootful socket) | Native socket `/var/run/docker.sock`. |
| macOS | **Colima** (`brew install colima docker docker-compose`) | Podman machine | Athena can run `colima start` and `colima status`. The socket is `~/.colima/default/docker.sock`. Volume paths must be under `$HOME` or a mount configured in Colima. |
| Windows | **Docker Engine inside WSL2** | Podman machine (WSL2 backend), Rancher Desktop (dockerd mode) | Docker Desktop is excluded because it isn't open source. Athena connects over a TCP/npipe endpoint or a relayed socket exposed by the WSL distro. Windows paths are translated to `/mnt/<drive>/…` for bind mounts. |

**Windows (decided: detect only).** Athena does not install a runtime. It detects Docker Engine in a WSL2 distro, Podman machine, or Rancher Desktop (dockerd mode), in that order of preference, and connects to the first one that responds. When none is found, the `containers` capability is `missing`, and the setup wizard shows step-by-step instructions for installing Docker Engine in WSL2 or Podman. Provisioning a WSL distro automatically is a possible post-MVP feature. Windows containers are out of scope; only Linux containers are supported.

### Package managers per OS

| OS | Detected |
|---|---|
| Linux | apt, dnf, pacman, zypper, apk, flatpak, snap, brew (Linuxbrew) |
| macOS | brew (formulae + casks) |
| Windows | winget, scoop, choco |

Each one implements the same interface:

```python
class PackageManager(Protocol):
    id: str
    def search(self, q: str) -> list[PackageRef]: ...
    def installed(self) -> list[InstalledPackage]: ...
    def upgradable(self) -> list[InstalledPackage]: ...
    async def install(self, pkg: str, job: Job) -> None: ...
    async def uninstall(self, pkg: str, job: Job) -> None: ...
    async def upgrade(self, pkg: str | None, job: Job) -> None: ...
```

Use machine-readable output where it exists (`brew --json`, `winget --output json`…). Otherwise parse stable output formats, and pin those formats down in fixtures-based tests.

**As built (M5 part A).** `athena/packages/` (`base.py`, `linux.py`, `apps.py`, `windows.py`; `MANAGERS` keyed by capability id). Reads go through an async runner (no shell, `LC_ALL=C.UTF-8`, 120 s timeout) into pure parsers; changes are argv lists run as jobs, one job per manager at a time. Package names must start with a letter or digit, so nothing reaches a CLI as an option.

| Manager | Search | Installed | Upgradable | Notes |
|---|---|---|---|---|
| apt | `apt-cache search` (regex-escaped) | `dpkg-query -W -f` (tab format, `ii`/`hi` only) | `apt-get -s upgrade` `Inst` lines (`apt list` says its CLI isn't stable) | `DEBIAN_FRONTEND=noninteractive`, keeps existing conffiles; refresh = `apt-get update` |
| dnf | `dnf repoquery --qf` with real tab/newline characters (dnf5 doesn't expand `\t`; dnf4 adds a blank line) | `rpm -qa --qf` | `repoquery --upgrades` | Works on dnf4 and dnf5; refresh = `makecache` |
| zypper | `--xmlout search` (exit 104 = none) | `rpm -qa` | `--xmlout list-updates` | |
| pacman | `pacman -Ss` (regex-escaped) | `pacman -Q` | `pacman -Qu` | Installs use `-Syu --needed` and there's no single-package upgrade: Arch doesn't support partial upgrades |
| apk | `apk search -v` | `apk list --installed` (skips virtual `.deps`) | `apk list --upgradable` | |
| brew | `brew search`, then `brew info --json=v2` for the top 30 (`--desc` takes ~10 s) | `brew info --json=v2 --installed` | `brew outdated --json=v2` | Casks install with `--cask`; refresh = `brew update` |
| flatpak | `search --columns=…` (tabs) | `list --app --columns=…` | `remote-ls --updates` | Installs from the result's remote (default flathub) |
| snap | `snap find` (column table) | `snap list` | `snap refresh --list` | |
| winget | `winget search` (positional columns, so localized headers work) | `winget list` | `winget upgrade` | `--accept-*-agreements --disable-interactivity`; "no package found" isn't an error. Ids of locally installed apps contain spaces (`ARP\Machine\X64\Mozilla Firefox`); ids winget shortens with `…` can't be acted on, so the UI disables those rows |
| scoop | `scoop search` (dash-row table) | `scoop export` (JSON) | `scoop status` | `.cmd` shim resolved with `shutil.which` |
| choco | `--limit-output` (`name\|version`) | `choco list -r` | `choco outdated -r` | Machine-wide: needs an elevated Athena |

Fixtures (`tests/fixtures/packages/`, README says how each was captured): brew, apt, apk, dnf (4 and 5), zypper, pacman and flatpak search are real recordings, made in throwaway containers from the distros' own registries; winget's list is a real recording from the Windows CI runner; snap, Scoop, Chocolatey and the other winget files are hand-written from documented formats. Read-only tests run the real tool where it exists (brew on macOS, apt on Ubuntu, choco and winget on Windows CI). The first CI run caught a wrong assumption (winget ids can contain spaces), which is how the real winget fixture was captured.

### Privilege model

| OS | Athena runs as | Privileged ops |
|---|---|---|
| Linux | `root` systemd service, which is what CasaOS does too | Direct |
| macOS | The logged-in user, as a launchd agent | Not needed: brew refuses to run as root and Colima is per-user |
| Windows | The logged-in user, through a Scheduled Task at logon | winget/scoop are per-user. Machine-wide installs raise UAC on the desktop, and the UI warns about that |

The manifest reports `needs_privilege` when an operation can't be done as the current user.

---

## 4. Feature design

### 4.1 Apps and the app store

**App definition format.** A standard `compose.yaml` plus an `x-athena` extension, so any compose file works as a custom app with zero metadata:

```yaml
name: jellyfin
x-athena:
  title: Jellyfin
  icon: https://…/jellyfin.svg
  category: media
  description: Free software media system
  port_web: 8096          # what "Open" links to
  platforms: [linux/amd64, linux/arm64]
  env_schema:             # renders the install form
    - key: TZ
      label: Timezone
      default: "{{ host.timezone }}"
  volumes_hint:
    - target: /media
      label: Media library
services:
  jellyfin:
    image: jellyfin/jellyfin:10.10
    ports: ["8096:8096"]
    volumes:
      - "{{ athena.data }}/jellyfin/config:/config"
```

- **Catalogs** are Git repos or HTTP URLs that contain `apps/<id>/compose.yaml`. Athena ships one built-in catalog, `catalog/` in this repo, with about 20 curated apps, and users can add more.
- **CasaOS compatibility.** An importer maps CasaOS `x-casaos` metadata to `x-athena`, so the CasaOS AppStore (Apache-2.0) can be added as a catalog. Umbrel's store is **not** included because its license is non-commercial.
- **Install flow:** render the form from `env_schema`, resolve templates, then write the result to `<data>/apps/<id>/compose.yaml`. After that, `compose up -d` runs as a job, and the app is recorded in SQLite.
- **Custom apps:**
  - *Paste or upload compose* → validated, then edited in a CodeMirror editor before deploy.
  - *Import `docker run …`* → a Python parser (shlex plus a flag map, the same idea as `composerize`) turns it into compose that the user reviews.
- **Path portability.** `{{ athena.data }}` resolves per OS: `/var/lib/athena` on Linux, `~/Library/Application Support/Athena` on macOS (inside Colima's shared mount) and `%LOCALAPPDATA%\Athena` on Windows (translated for WSL).

### 4.2 Terminal

- Backend: a WebSocket at `/api/terminal/ws?target=host|container:<id>`. On POSIX it uses the stdlib pty, and on Windows it uses `pywinpty` (ConPTY) running PowerShell 7, or Windows PowerShell when 7 isn't installed. A container shell runs `docker exec -it` through the same CLI as the rest of Athena, so Docker in WSL works too.
- Frontend: `xterm.js` with the fit and web-links addons, themed from the active CSS variables.
- Admin only, and it can be turned off globally in settings.

**As built (M5):**
- `athena/terminal/pty.py` (`PtySession`) gives one async interface over both OSes.
  - A reader thread feeds a bounded queue, so a slow browser stalls the program instead of filling memory.
  - Writes run in a thread.
  - Closing hangs up the whole session (SIGHUP to the process group, then SIGKILL).
  - POSIX doesn't use `pty.fork()` or ptyprocess. Forking the multi-threaded server and running Python in the child can deadlock it. `subprocess.Popen(start_new_session=True)` forks and execs in C, and a two-line shim (`TIOCSCTTY`, then `execvp`) makes the pty the controlling terminal, so Ctrl+C and job control work. A missing program exits 127.
- `athena/terminal/shells.py` chooses what to run:
  - On the host, the service user's login shell (`-l`); `/bin/sh` if it's missing or `nologin`.
  - In a container, bash if the image has it, otherwise sh, with `TERM=xterm-256color`.
- The protocol:
  - After connecting, the browser sends `{"type":"auth","csrf","cols","rows"}` with the session's CSRF token. Browsers can't set headers on a WebSocket, and a cross-site page can't read the token.
  - The server sends `{"type":"ready"}`, then output as binary frames.
  - The browser sends `{"type":"input"}` and `{"type":"resize"}` text frames.
  - When the program exits, the server sends `{"type":"exit","code"}` and closes with 1000.
- Close codes, shown to the user with their reason:
  - 4401: no session, or signed out.
  - 4403: bad CSRF token, or not an admin.
  - 4404: bad target.
  - 4409: turned off, unsupported, or the runtime isn't ready.
  - 4429: more than 10 open terminals.
  - 4500: the program couldn't start.
- Session checks while a terminal is open:
  - Signing out, or the session expiring, closes it within 60 s.
  - Turning the terminal off (`PUT /api/settings/system`) closes every open terminal at once.
- Audit: `terminal.open` and `terminal.close` (exit code or reason, duration), with target `host` or `container:<ref>`; `settings.terminal` on/off.
- UI:
  - `/terminal` (nav item gated by `terminal.host`) with a status badge and New session.
  - A **Shell** action on running containers, both on the Containers page and in app detail, opening a sheet.
  - Settings → System holds the switch.
  - `<Terminal>` in `packages/ui/.../athena/terminal.tsx` themes xterm.js from the CSS variables (converted to rgba through a canvas so oklch works) and re-themes when `<html>` attributes change. The ANSI hues are two fixed palettes, chosen by background lightness. Links in output (OSC 8 and plain URLs) open only if they're http(s), in a new tab with no opener; program output is untrusted, and xterm's default OSC 8 handler would also follow `javascript:`.

### 4.3 Files and sharing

- **File manager** API rooted at configured "locations", never the entire filesystem by default. Endpoints: list, stat, read, upload (chunked), download, mkdir, move, copy, delete (to trash where the OS supports it via `send2trash`).
- **Share links:** a token, an optional password, expiry and read-only or upload-only modes. Served by `/s/<token>`.
- **Network share:** WebDAV via `wsgidav`, mounted inside the server. It's one implementation that works on all three OSes and is mountable from Finder, Windows Explorer and Linux file managers. SMB and NFS are post-MVP and only offered where the OS has them, through the capability manifest.

### 4.4 Cloud storage

- Run `rclone rcd` as a managed child process, bound to localhost with random credentials, and drive it over its HTTP API.
- MVP: add, edit and remove remotes (OAuth handled by rclone's config flow), browse a remote in the same file manager UI, and copy/sync jobs between local and remote with progress over SSE.
- **Mounts come later** because they need FUSE: libfuse on Linux and WinFsp (GPL with FLOSS exception) on Windows. On macOS the open-source path is `rclone nfsmount`, since macFUSE is not open source.

### 4.5 AI assistant

- `pydantic-ai` + `pydantic-ai-harness`. The model provider is configured in settings: Anthropic, OpenAI, or local **Ollama** for fully offline use.
- **Tools are Athena's service layer, not raw shell by default.** Examples: `list_apps`, `app_logs`, `install_catalog_app`, `deploy_compose`, `search_packages`, `install_package`, `list_files`, `system_stats`, `capabilities`. They're registered from the capability manifest.
- **Safety:**
  - Read-only tools run freely.
  - Mutating tools are *deferred tools* that need human approval: the UI shows an approve/deny card with the exact action.
  - The harness's Shell capability is opt-in in settings. It uses an allowlist and still needs approval for every call.
  - The harness's spend-limit and loop-detection capabilities are enabled.
- **Transport:** Pydantic AI's Vercel AI SDK adapter streams to the frontend, and the chat UI uses AI SDK `useChat`.
- **Persistence:** conversations are stored in SQLite.

### 4.6 Dashboard

- `athena/monitor.py`: `psutil` for CPU, memory, swap, disks, network, disk I/O, load and temperatures, sampled every 2 s by a background task started in the app lifespan. A ring buffer keeps 1 h of samples (1800) for sparklines.
  - `GET /api/system/stats` returns the current stats plus the history; `GET /api/system/stats/stream` (SSE) sends a `stats` event after each sample. After a dropped stream the UI reloads the snapshot to fill the gap.
  - No capability: psutil covers all three OSes. Metrics a host can't report are `null` and hidden (temperatures exist only on Linux; disk I/O counters can be missing on Windows and in containers).
  - Memory "used" is total − available. Network totals skip loopback and container bridges (`veth*`, `docker*`, `br-*`, `vEthernet*`), which would double count.
  - Disks: physical partitions only, minus pseudo/snap/image filesystems, macOS `dontbrowse` volumes and read-only mounts other than `/`; partitions with identical total and free space (APFS volumes in one container, bind mounts) collapse to the shortest mount point; used = total − free. Refreshed every 30 s.
- Cards: system stats (CPU, memory, network, disk activity, each with a 5 min / 1 h sparkline), apps, storage, temperatures (when reported), server info with uptime, capabilities.
- Apps card: one tile per app with its store icon and title (`AppOut.title`/`icon`, looked up from the catalog; plain compose apps fall back to initials), status, Open links and a one-click start/stop. When the runtime isn't ready it shows the same Start/setup panel as the Apps page; it's hidden where containers are unsupported, like the Apps nav item.

---

## 5. Frontend

### 5.1 Monorepo bootstrap

```bash
pnpm dlx shadcn@latest init --preset b0 --template next   # choose the monorepo option
```

This produces `apps/web` and `packages/ui`. Then:

- `apps/web/next.config.ts` → `output: "export"`, `images.unoptimized: true`
- add `packages/api-client` (generated)
- Turborepo tasks: `dev`, `build`, `lint`, `typecheck`, `gen:api`

### 5.2 App shell from the `dashboard-01` block

The sidebar, header and app layout come from the shadcn `dashboard-01` block, added to the web app:

```bash
pnpm dlx shadcn@latest add dashboard-01 -c apps/web
```

The CLI rewrites the block's Tabler icons to whatever icon library the preset uses. What happens to each file the block adds:

| Block file | What Athena does with it |
|---|---|
| `components/app-sidebar.tsx` | **Keep.** Replace the demo `data` object with nav built from the capability manifest. Missing features don't render. Put the Athena logo and name in the header |
| `components/nav-main.tsx` | **Keep.** Primary nav: Dashboard, Apps, Store, Packages, Files, Cloud, Terminal, Assistant. Swap the "Quick Create" button for "Add app" (store / custom) |
| `components/nav-secondary.tsx` | **Keep.** Settings, plus a link to help/docs |
| `components/nav-user.tsx` | **Keep.** Bind it to the logged-in user, with Account and Log out |
| `components/site-header.tsx` | **Keep.** Breadcrumb/page title, ⌘K command palette trigger, runtime status badge, assistant toggle |
| `components/nav-documents.tsx` | **Delete.** It's the block's demo document list |
| `app/dashboard/page.tsx` | **Delete.** Athena's own dashboard is `app/(app)/page.tsx` |
| `app/dashboard/data.json` | **Delete.** Demo data |
| `components/section-cards.tsx`, `chart-area-interactive.tsx`, `data-table.tsx` | **Delete.** They're demo dashboard content. Athena builds its own stats cards, charts and tables from shadcn `card`, `chart` and `table`, wired to the API |

Layout: `app/(app)/layout.tsx` holds `SidebarProvider` + `AppSidebar` (variant `inset`) + `SidebarInset` + `SiteHeader`. Every authenticated route lives under that layout. `/setup` and `/login` sit outside it.

Packages the block pulls in that Athena doesn't need, such as `@dnd-kit/*` (only the demo table's row drag uses it), are removed after the add.

### 5.3 Components: shadcn first, create only what's missing

| Need | Source |
|---|---|
| App shell, nav | `dashboard-01` block (see 5.2), plus shadcn `command` for the ⌘K palette |
| Stats | shadcn `card`, `chart` (Recharts), `progress`, `badge`, `skeleton` |
| Lists | shadcn `table` + TanStack Table (the shadcn *data-table* pattern), `empty`, `item`, `pagination` |
| Forms | shadcn `field`, `input`, `select`, `combobox`, `switch`, `textarea`, `input-group`, `radio-group` |
| Overlays | shadcn `dialog`, `sheet`, `alert-dialog`, `popover`, `tooltip`, `sonner` |
| Layout | shadcn `tabs`, `resizable`, `scroll-area`, `separator`, `accordion` |
| AI chat | **AI Elements** registry (shadcn-compatible, Apache-2.0): `conversation`, `message`, `prompt-input`, `tool`, `confirmation`, `reasoning` |
| Terminal | **Create:** `<Terminal>` wrapping xterm.js, themed from CSS vars |
| Code/compose editor | **Create:** `<CodeEditor>` wrapping CodeMirror 6 (YAML lang, lint) |
| File browser | **Create:** `<FileBrowser>` built from table, breadcrumb, context-menu, dropzone |
| App store card / app tile | **Create:** composed from card, badge, button |
| Log viewer | **Create:** virtualized `<LogStream>` (ANSI → spans) |
| Job progress | **Create:** `<JobToast>` on top of sonner + progress |

The rule: run `pnpm dlx shadcn@latest search` (and the AI Elements registry) before writing anything. Created components go into `packages/ui/src/components/athena/` and use only theme tokens.

### 5.4 Runtime appearance settings

shadcn presets are applied at *init/build time* by the CLI. Athena needs them switchable *at runtime* from Settings, so they're turned into data attributes and CSS variables:

| Setting | Runtime mechanism |
|---|---|
| Light/dark/system | `next-themes` (`class` attribute) |
| Base color | `[data-base="neutral|stone|zinc|mauve|olive|…"]` blocks that set `--background`, `--foreground`, `--muted`, `--border`… |
| Theme (accent) | `[data-theme="…"]` blocks that set `--primary`, `--ring`, `--sidebar-primary`… |
| Chart color | `[data-chart="…"]` blocks that set `--chart-1…5` |
| Body / heading font | All curated fonts loaded with `next/font` as CSS variables, then `[data-font="inter"]` → `--font-sans`, `[data-font-heading="…"]` → `--font-heading` |
| Radius | `[data-radius]` → `--radius` |
| Style (mira, luma, …) | **Spike needed.** See below |

- **Generated CSS (M4).** `scripts/gen-theme-css.mjs` (`pnpm gen:theme`) asks the registry's `/init` endpoint (what the shadcn CLI uses) for every base color, theme, chart color and radius, and writes `packages/ui/src/styles/themes.css` plus `themes.json` (the options and swatches the Settings page offers). Both are committed, so builds don't need the network; rerun after upgrading shadcn. Nothing is hand-copied.
  - The registry's model, found by probing: a theme is a colored accent (17) or the base color's own name ("match base", valid only with that base); explicit chart colors work the same way, and `neutral` charts means "follow the theme" (sent as no `chartColor`). `gray` is in the preset lists but the registry refuses it, so it's skipped.
  - Base blocks carry every variable; theme blocks carry what each theme actually sets, worked out per mode on two bases (most set primary, secondary, sidebar-primary and the charts; rose also sets the dark sidebar); chart blocks come last and override. The script verifies every colored theme on a third base, plus an explicit chart, against the registry and fails if they don't compose.
  - Selectors are `:root[data-base=…]` and `:root.dark[data-base=…]` (and the same for theme, chart, radius), which beat the `:root`/`.dark` defaults in `globals.css` without `!important`.
- **Fonts (M4).** All 26 preset fonts are self-hosted with `next/font` (`apps/web/lib/fonts.ts`) as `--font-<id>`; only Inter and Geist Mono are preloaded, so another font's files load the first time a page uses it. `[data-font]` sets `--font-sans`, `[data-font-heading]` sets `--app-font-heading`, and `globals.css` maps Tailwind's `font-heading` to it (Tailwind inlines `@theme inline` values, so the utility has to read a runtime variable). A `satisfies` check fails the build if shadcn adds a font.
- **Persistence (M4).** Saved per user (`users.appearance`, JSON; `GET/PUT /api/settings/appearance`). The server only checks the id shape; the UI normalizes unknown ids to the defaults. An inline script in `<head>` (`APPEARANCE_SCRIPT`) copies the browser's last-known settings onto `<html>` before first paint (verified: the attributes are set when `<body>` starts parsing); signed in, the account's settings are fetched and win. Changes apply instantly and are saved 400 ms after the last one. Dark/light/system stays with `next-themes`.
- **Preset codes (M4).** `shadcn/preset` (`encodePreset`/`decodePreset`, pure and browser-safe) runs in the browser. Export keeps b0's style, icons and menus; import applies colors, fonts and radius and reports what it skipped (another style, icon library, menu colors, or an option the registry doesn't serve).
- **Style (decided: one style in the MVP).** Styles change component class names and spacing, not just variables, so the MVP ships the style from preset `b0` only. The Style field in Settings shows the current style as read-only, with a "coming later" note. Post-MVP option: generate a `packages/ui` build per style and swap them by attribute-scoped CSS.

### 5.5 Routes

```
/setup                    first-run wizard (admin, runtime, data dir)
/login
/                         dashboard
/apps                     installed apps
/apps/[id]                details · logs · terminal · compose · settings
/store                    catalog browse/search
/store/[catalog]/[app]    app page + install
/apps/new                 custom app (compose / docker run import)
/packages                 tabs per detected manager
/files                    file manager (locations + cloud remotes)
/shares                   share links + WebDAV
/cloud                    rclone remotes + sync jobs
/terminal                 host terminal
/assistant                full-page chat (also available as a sheet everywhere)
/settings/{appearance,account,ai,catalogs,system}
```

Static export doesn't allow dynamic segments without `generateStaticParams`. The workaround is query params (`/apps/view?id=…`) or a catch-all with client routing. **Decision: use query params for detail pages.**

---

## 6. Backend layout and API

```
apps/server/
  pyproject.toml            # uv project; entry point `athena`
  src/athena/
    main.py                 # FastAPI app, static mount, lifespan (detect, rclone, jobs)
    config.py               # pydantic-settings; per-OS data dirs (platformdirs)
    db.py                   # SQLModel + SQLite, Alembic migrations
    auth/                   # argon2 hashing, session cookie, CSRF
    platform/               # detect.py, capabilities.py, paths.py
    providers/
      containers/           # base.py, docker_api.py, colima.py, podman.py, wsl.py
      packages/             # base.py, apt.py, dnf.py, pacman.py, zypper.py, apk.py,
                            # brew.py, winget.py, scoop.py, choco.py, flatpak.py, snap.py
      terminal/             # posix.py, windows.py
      storage/              # rclone.py
    services/               # apps.py, catalog.py, compose_import.py, files.py,
                            # shares.py, monitor.py, jobs.py
    assistant/              # agent.py, tools.py, approval.py
    api/                    # routers, one per service
  tests/                    # pytest; provider tests use recorded CLI fixtures
catalog/                    # built-in app catalog
```

API surface:

```
GET  /api/system/capabilities        POST /api/system/capabilities/refresh
GET  /api/system/stats   GET /api/system/stats/stream (SSE)   POST /api/runtime/{start|stop|setup}
GET  /api/apps                       POST /api/apps            (compose or catalog ref)
POST /api/apps/{id}/{start|stop|restart|update}   DELETE /api/apps/{id}
GET  /api/apps/{id}/logs (SSE)       POST /api/apps/import/docker-run
GET  /api/catalogs   POST /api/catalogs   GET /api/catalogs/{id}/apps
GET  /api/packages                   GET /api/packages/{mgr}/{installed|upgradable}
GET  /api/packages/{mgr}/search?q=   POST /api/packages/{mgr}/{install|uninstall|upgrade|refresh} (jobs)
WS   /api/terminal/ws?target=host|container:{id}
GET  /api/files?path=  POST /api/files/upload  …           (file ops)
GET/POST/DELETE /api/shares          /dav/…  (WebDAV)       /s/{token}
GET/POST/DELETE /api/cloud/remotes   POST /api/cloud/jobs
POST /api/assistant/chat (stream)    POST /api/assistant/approve/{call_id}
GET  /api/jobs/{id}  GET /api/jobs/{id}/events (SSE)
GET/PUT /api/settings/{appearance|ai|system}   POST /api/auth/password
```

---

## 7. Security baseline

- Binds to LAN by default. First run forces the admin account to be created before anything else is reachable.
- Session cookies are `HttpOnly` and `SameSite=Strict`, with CSRF tokens on mutating requests and login rate limiting.
- The terminal, package installs and the assistant's shell are the most powerful features. They're admin-only, each can be toggled off, and every use is written to an audit log table.
- The rclone rcd and container sockets are never exposed beyond localhost.
- Secrets (AI keys, rclone config) are encrypted at rest with a key from the OS keyring (`keyring`) when one is available.

---

## 8. Distribution (MVP)

- **Dev:** `pnpm dev` (Next on :3000, proxying `/api` to :8420) plus `uv run athena --reload`.
- **Release:** release-please tags a version from Conventional Commit PR titles. The release workflow then:
  1. builds the web app and copies `out/` into the Python package;
  2. builds the `athena_server-<version>-py3-none-any.whl` wheel;
  3. attaches the wheel and the install scripts to the GitHub release.
- **One-line install, CasaOS-style:**
  - Linux/macOS: `curl -fsSL https://github.com/tiagozaccaro/athena/releases/latest/download/install.sh | bash`. It needs `sudo` on Linux.
  - Windows: `irm …/install.ps1 | iex`.
  - The scripts install the runtime where the decisions allow it (Docker Engine on Linux, Colima on macOS; Windows is detect only), plus uv and the wheel through `uv tool install`, in Athena-owned directories.
  - They support `--version`, `--dry-run`, `--no-runtime`, and `--uninstall [--purge]`.
- **Service install:** `athena service install --data-dir --port` registers a systemd unit on Linux, a launchd agent on macOS, or a Scheduled Task at logon on Windows.
- **Later:** single-file binaries (PyInstaller/Nuitka) and native installers.

---

## 9. Dependency / license inventory

| Component | License |
|---|---|
| Next.js, React, shadcn/ui, Radix/Base UI, Tailwind, Recharts, TanStack Table | MIT |
| AI Elements, Vercel AI SDK | Apache-2.0 |
| xterm.js, CodeMirror 6, next-themes, openapi-typescript | MIT |
| shadcn CLI package (`shadcn/preset` used at runtime) | MIT |
| Preset fonts via `next/font/google` (Inter, Geist, Lora, Roboto and the other 22) | SIL OFL 1.1 / Apache-2.0 |
| Base UI (`@base-ui/react`), `cn`, Turborepo, openapi-fetch, lucide-react, sonner, zod | MIT / ISC |
| pydantic-settings, platformdirs, hatchling | MIT |
| SQLModel, SQLAlchemy, Alembic, argon2-cffi | MIT |
| python-on-whales, PyYAML | MIT |
| CodeMirror 6, @uiw/react-codemirror | MIT |
| dashboard-icons (catalog icons, loaded by URL) | Apache-2.0 |
| httpx2 (test client) | BSD-3-Clause |
| FastAPI, SQLModel, Pydantic, pydantic-ai, pydantic-ai-harness, uvicorn | MIT / BSD |
| Docker Engine (Moby), Docker CLI, Compose v2 | Apache-2.0 |
| python-on-whales, psutil, platformdirs, pywinpty (Windows only), send2trash | MIT / BSD / ISC |
| wsgidav | MIT |
| Colima, Lima | MIT / Apache-2.0 |
| Podman | Apache-2.0 |
| rclone | MIT |
| winget-cli, scoop, Chocolatey CLI | MIT / Unlicense / Apache-2.0 |
| Homebrew | BSD-2 |
| CasaOS AppStore (catalog data) | Apache-2.0 |
| ~~Docker Desktop, macFUSE, Umbrel apps~~ | Excluded (proprietary / non-commercial) |

---

## 10. Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Monorepo skeleton | shadcn init done, uv server, turbo, API client generation, CI on all 3 OSes (GitHub Actions matrix) |
| M1 | Platform + capabilities | The manifest is correct on Linux, macOS and Windows, the UI hides missing features, and the first-run wizard and login work |
| M2 | Containers + apps | Runtime detection on all OSes (start for Colima), Windows setup instructions, app lifecycle, logs, compose and docker-run import |
| M3 | App store | Built-in catalog, remote catalogs, CasaOS importer, install form |
| M4 | Dashboard + appearance | Live stats and charts. Runtime theme/base/chart/font/radius switching, plus the style decision |
| M5 | Packages + terminal | All detected managers with jobs. Host terminal and container exec on all OSes |
| M6 | Files, shares, cloud | File manager, share links, WebDAV, rclone remotes and copy/sync |
| M7 | AI assistant | Agent with service tools, approval flow, provider settings, streaming chat UI |

M2–M4 can proceed in parallel once M1 lands, and so can M5 and M6. M7 depends on the service layers it wraps.

---

## 11. Decisions log

| Question | Decision |
|---|---|
| shadcn style switching | One style (from preset `b0`) in the MVP. Colors, theme, chart colors, fonts and radius switch live |
| Windows container runtime | Detect only: Docker Engine in WSL2, Podman, or Rancher Desktop. Show instructions when none is found |
| Linux privilege | Run as a root systemd service (CasaOS-style) |
| Next.js mode | Static export served by FastAPI |
| shadcn primitives (M0) | Base UI (`base-nova` style from preset `b0`), lucide icons |
| Dev API access (M0) | `next.config.ts` adds an `/api` rewrite to the server in `next dev` only; builds are static exports with `trailingSlash: true`, served by FastAPI `StaticFiles` |
| Python (M0) | 3.13 for the server and the installers (`requires-python >= 3.12`) |
| Versioning (M0) | release-please `simple` type with `extra-files` that bump `pyproject.toml` and both `package.json` files; first release is 0.1.0 |
| Capability detection (M1) | All host access goes through `athena.platform.probe.Probe` (never raises); the Docker-compatible API is pinged directly over a unix socket or Windows named pipe, with no Docker SDK; the manifest lists only capabilities relevant to the host's OS |
| Auth (M1) | One admin, created on first run at `/setup`. Passwords use argon2id. The session cookie `athena_session` is a random token (only its SHA-256 is stored), HttpOnly, SameSite=Strict, Secure on HTTPS, with a 30-day TTL. A per-session CSRF token goes in the `X-CSRF-Token` header on writes. Failed logins are limited to 5 per client per 5 minutes. Public routes: `/api/health`, `/api/auth/*`, and the static UI |
| Container access (M2) | One CLI-based path for every runtime via `python-on-whales` (see §2 Decisions). The `containers` capability carries the engine `endpoint`. Container refs are validated against `^[A-Za-z0-9][A-Za-z0-9_.-]*$` before reaching the CLI |
| Apps (M2) | An app is a compose project in `<data-dir>/apps/<name>/compose.yaml` (previous version kept as `compose.prev.yaml`) plus an `apps` row. Compose runs with `ATHENA_APP_DATA=<data-dir>/apps/<name>/data`, so files can use `${ATHENA_APP_DATA}`. Validation is a structural check plus `docker compose config --quiet`. Lifecycle (deploy, edit, start, stop, restart, update = pull + up, remove with optional `--volumes` and data folder) runs as jobs, one per app at a time. `docker run` import is a shlex + flag-map converter with warnings for unsupported flags. On macOS, Colima only mounts `$HOME`, which the default data dir is under |
| App store format (M3) | Catalog apps are plain compose files with `x-athena` metadata (`title`, `description`, `category`, `icon`, `homepage`, `web_port`, `notes`, `env` fields). Install values use standard `${KEY}` interpolation and are written to `.env` (mode 600) next to `compose.yaml`; no custom template syntax. Default tokens: `@timezone`, `@uid`/`@gid`, `@app_data[/sub]`; `generate: secret` fills passwords. Every `${…}` must be declared or `ATHENA_APP_DATA`. The built-in catalog is `catalog/` at the repo root (20 apps, see `catalog/README.md`), bundled into the wheel as `athena/catalog_builtin`. Icons come from dashboard-icons (Apache-2.0) via jsDelivr |
| Remote catalogs (M3) | Downloaded as an archive over HTTPS (no git): GitHub/Codeberg/GitLab repo URLs are turned into archive URLs; direct .tar.gz/.zip links work. Safe extraction (no traversal or links, 200 MB download, 50k files, 1 GB extracted). The folder holding `apps/` (Athena) or `Apps/` (CasaOS) is found up to 8 levels deep, normalized into `<data-dir>/catalogs/<id>/apps/*/compose.yaml`, and swapped in atomically; a failed refresh keeps the previous copy and records the error. Refresh runs as a job |
| CasaOS import (M3) | `x-casaos` converted to `x-athena`: `/DATA/AppData/$AppID` becomes `${ATHENA_APP_DATA}`, `/DATA/<X>` becomes a path field, `port_map` becomes `WEB_PORT`, `$PUID/$PGID/$TZ` become default-token fields, and other variables become fields (secrets generated). Parsed with YAML 1.2 booleans like compose. The one-click source is the official CasaOS-AppStore release `main.zip` (182 apps, all pass `compose config`); the full repo is too large and the pruned `_appstore` mirror is unlicensed. Imported files keep upstream specifics (e.g. Raspberry Pi device mappings) |
| Host stats (M4) | psutil sampled every 2 s into a 1 h ring buffer; JSON snapshot with history plus an SSE stream of `stats` events. No capability (psutil runs on all OSes); unavailable metrics are `null`. Disks are filtered and de-duplicated by (total, free) so APFS volumes show once |
| Package managers (M5) | One class per manager over a shared async runner and pure parsers pinned by fixtures (real recordings where a container could produce them). Machine-readable output where it exists (brew JSON, zypper XML, scoop export, choco `-r`), otherwise stable formats (`dpkg-query`, `rpm --qf`, `apt-get -s`). One job per manager at a time; installs, uninstalls, upgrades and refreshes are audited as `package.<action>` with `<manager>:<name>`. The Packages nav item shows when any `packages.*` capability is present (`capability: "packages.*"`) |
| Runtime appearance (M4) | Theme CSS generated from the shadcn registry's `/init` endpoint by `scripts/gen-theme-css.mjs` into committed `themes.css`/`themes.json`, verified against the registry when generated; data attributes on `<html>`, applied before paint by an inline script; saved per user in `users.appearance`; preset codes via `shadcn/preset` in the browser. Style, icons and menus stay b0's |
| Password change (M4) | `POST /api/auth/password` needs the current password (wrong one is 400, not 401, so the UI doesn't sign out; failures count toward the login throttle), signs out the user's other sessions and keeps this one; audited as `auth.password` |
| Server shutdown (M4) | `athena serve` sets uvicorn `timeout_graceful_shutdown` to 5 s. SSE streams never end on their own, so without it an open dashboard kept the server (and a service stop or restart) waiting forever |
| Jobs (M2) | In-memory job runner (`athena.jobs`) with output lines streamed over SSE (`/api/jobs/{id}/events`); the last 100 finished jobs are kept. The durable record of privileged actions is the `audit_log` table |
| Terminal pty (M5) | Stdlib pty with `subprocess.Popen(start_new_session=True)` and a `TIOCSCTTY` exec shim on POSIX, instead of ptyprocess. `pty.fork()` in the multi-threaded server runs Python in the child (Python 3.12+ warns that this can deadlock). pywinpty (ConPTY) on Windows |
| Terminal auth (M5) | The WebSocket checks the cookie itself (`require_user` can't apply to WebSockets), then requires the CSRF token in the first message. Admin only. Signing out closes open terminals within 60 s, and turning the terminal off closes them at once. Container shells use `docker exec -it` through the runtime CLI, not the Docker API, matching the M2 CLI decision |
| System settings (M5) | One JSON row in the `system_settings` table (migration 0007), behind `GET/PUT /api/settings/system`. Only admins can change it. It holds `terminal_enabled` for now; the package-install and assistant-shell switches from §7 will join it |
| Database (M1) | SQLite at `<data-dir>/athena.db` (WAL, foreign keys on), SQLModel models, Alembic migrations run on every start from code. A test fails if models and migrations drift |

## 12. Open questions

1. **Default AI provider:** the provider is configurable either way. Should the first-run wizard suggest a cloud provider (Anthropic/OpenAI key) or local Ollama first?
