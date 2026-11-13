---
name: athena-platform-feature
description: Adds or changes an Athena feature that touches the host OS (container runtimes, package managers, terminal, file shares, cloud storage, system stats) so it works on Linux, macOS and Windows and is gated by the capability manifest. Use when adding a provider under apps/server/src/athena/providers, a new capability id, a new package manager or container runtime, an AI assistant tool that acts on the host, or any UI that should only appear when the host supports it.
---

# Athena platform feature

Athena runs on Linux, macOS and Windows. Every host-facing feature follows the same path:

```
platform/detect → Capability in the manifest → provider (per OS) → service → API router
                                                                  ↘ assistant tool (same gate)
                                         UI reads GET /api/system/capabilities and hides what's missing
```

The design is in `docs/mvp-design.md` (§3 Platform layer, §4 Features). Read the relevant section first.

## Checklist

1. **Capability id.** Pick a dotted id (`containers`, `packages.winget`, `terminal.host`, `shares.webdav`, `cloud.rclone`). Add detection in `platform/detect.py`:
   - Probe with `shutil.which`, socket or HTTP checks, and a version command with a short timeout.
   - Return `status` as one of `ready | stopped | missing | unsupported | needs_privilege`, plus `actions` the UI can offer (`start`, `setup`).
   - Never raise from detection; a failed probe means `missing` with a `detail` string.
2. **Provider.** Implement the shared Protocol in `providers/<area>/base.py` in its own module (`providers/packages/winget.py`).
   - Use subprocess with argument lists, never `shell=True`. Prefer machine-readable output (`--json`, `--output json`).
   - Long operations take a `Job` and stream progress lines; they must be cancellable.
   - Paths go through `platform/paths.py` (platformdirs, WSL path translation on Windows, Colima-shared mounts on macOS).
3. **Register** the provider in the area's registry keyed by capability id, so services and the assistant look it up from the manifest instead of branching on `sys.platform`.
4. **Service + router.** Services hold logic; routers stay thin. Mutating endpoints return a `job_id`.
5. **Assistant tool** (if useful). Register it only when the capability is `ready`. Read-only tools run freely. Mutating tools must be deferred tools that need user approval.
6. **UI.** Gate the nav item, page and buttons on the capability via the `useCapability(id)` hook. A missing capability renders shadcn `empty` with the `detail` and any setup action, never a broken page.
7. **Tests.**
   - Provider parsing tests use recorded CLI output fixtures in `tests/fixtures/<manager>/`, so they run on every OS.
   - Detection tests mock `shutil.which` and subprocess.
   - Mark tests that need the real tool with `@pytest.mark.requires("<capability>")` so CI skips them where it's absent.

## Rules

- Open-source dependencies only. Not allowed: Docker Desktop, macFUSE, non-commercial licensed catalogs. Add any new dependency to the license table in `docs/mvp-design.md` §9.
- Container engines are reached through the Docker API socket (Docker Engine, Colima, Podman, WSL dockerd). Compose goes through `python-on-whales`.
- Windows: detect only. Athena never installs a container runtime there. Show setup instructions instead.
- Linux runs as root. macOS and Windows run as the logged-in user. Report `needs_privilege` instead of escalating silently.
