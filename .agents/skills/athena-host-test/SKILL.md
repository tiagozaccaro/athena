---
name: athena-host-test
description: Tests Athena on a real Linux, macOS or Windows host instead of only in unit tests - the one-line installers, the system service, capability detection and package managers (apt, dnf, pacman, zypper, apk) - using a throwaway Lima VM locally or the E2E GitHub workflow. Use when a change touches scripts/install.sh, scripts/install.ps1, `athena service`, platform detection or a package manager, or when docs/STATUS.md lists something as "not verified on a real host".
---

# Test on a real host

Unit tests and fixtures prove the parsers. This proves the real installer, service and tools work. Pick the route:

| Need | Route |
|---|---|
| Linux with systemd (Ubuntu, Fedora, Arch, openSUSE, Alpine) | **Lima VM** on the developer's Mac (below) |
| Windows, Ubuntu or macOS runners, scripted | **E2E workflow** on GitHub (below) |
| Windows desktop features (Docker in WSL, Explorer WebDAV mount) | Not possible from an agent. List it in STATUS as a manual check for the maintainer |

Docker containers are **not** a substitute: they have no systemd, so the service install can't be tested in them. They're fine for recording package-manager fixtures (see `apps/server/tests/fixtures/packages/README.md`).

## 1. Build what you're testing

Test the commit, not the last release:

```bash
pnpm install --frozen-lockfile
scripts/build-wheel.sh               # -> dist/athena_server-<v>-py3-none-any.whl (UI + catalog bundled)
```

## 2a. Lima VM (local Linux)

```bash
limactl list                                         # reuse an existing athena-* VM if there is one
limactl start --name athena-ubuntu --tty=false --cpus 4 --memory 4 template://ubuntu-24.04
#   other distros: template://fedora (dnf), template://archlinux (pacman),
#   template://opensuse (zypper), template://alpine (apk; OpenRC, not systemd)
```

- Lima mounts the Mac's home folder read-only in the VM at the same path, so the repo and `dist/` are visible as they are.
- Lima forwards the VM's listening ports to the Mac's `localhost`. The VM's Athena on 8420 shows up as the Mac's `localhost:8420` and can clash with a local Athena. Check `lsof -nP -iTCP:8420 -sTCP:LISTEN` first.

Install and check:

```bash
WHEEL=$(ls "$PWD"/dist/athena_server-*.whl)
limactl shell athena-ubuntu -- sudo bash "$PWD/scripts/install.sh" --wheel "$WHEEL"
limactl shell athena-ubuntu -- bash -c 'systemctl is-active athena; sudo athena service status; curl -s localhost:8420/api/health'
```

Browser smoke test (from the Mac, through the forwarded port; the data dir must be fresh):

```bash
uv run --with playwright==1.65.2 playwright install chromium    # once
uv run scripts/e2e/smoke.py --url http://localhost:8420 --out e2e-out --expect terminal.host --expect containers
```

API checks inside the VM (package install as a job, then confirm with the real tool):

```bash
limactl shell athena-ubuntu -- bash -s <<'EOF'
set -e; cd /tmp; B=http://localhost:8420
curl -s -c jar -o login.json -H 'content-type: application/json' \
  -d '{"username":"admin","password":"e2e-test-pass-1234"}' $B/api/auth/login
CSRF=$(jq -r .csrf_token login.json)          # sudo apt-get install -y jq, if missing
curl -s -b jar -o caps.json $B/api/system/capabilities && jq '.' caps.json | head -40
curl -s -b jar -X POST -H "X-CSRF-Token: $CSRF" -H 'content-type: application/json' \
  -d '{"name":"sl"}' $B/api/packages/apt/install        # returns a job; poll GET $B/api/jobs/<id>
EOF
limactl shell athena-ubuntu -- dpkg -s sl | head -3     # the side effect, checked outside Athena
```

Uninstall check, then clean up:

```bash
limactl shell athena-ubuntu -- sudo bash "$PWD/scripts/install.sh" --uninstall --purge
limactl shell athena-ubuntu -- bash -c 'ls /etc/systemd/system/athena.service /var/lib/athena /opt/athena /usr/local/bin/athena 2>&1; curl -s -m 3 localhost:8420/api/health || echo "port closed"'
limactl stop athena-ubuntu && limactl delete athena-ubuntu     # only VMs you created
```

The installer flags are `--version`, `--wheel <path|url>`, `--no-runtime`, `--dry-run`, `--uninstall` and `--purge`. On Windows, `install.ps1` takes `-Version`, `-Wheel`, `-DryRun`, `-Uninstall` and `-Purge`.

## 2b. E2E workflow (GitHub runners: Ubuntu, macOS, Windows Server)

```bash
gh workflow run E2E --ref <branch>                  # also runs by itself on installer/service changes
gh run list --workflow E2E --branch <branch> --limit 1
gh run watch <run-id>; gh run view <run-id> --log-failed | tail -80
gh run download <run-id> -D e2e-artifacts            # screenshots, capabilities.json, logs
```

Limits: hosted runners can't run Colima (macOS) or WSL2 (Windows), so containers are only checked end to end on Ubuntu.

## 3. Record the result

- Put what you verified, and on which OS and version, in `docs/STATUS.md`, and take the item off "Not yet verified".
- A real-host bug that unit tests missed usually deserves a test plus an AGENT-NOTES bullet. One example: Windows `schtasks /End` left the real interpreter running.
- Delete `e2e-out/` and `e2e-artifacts/`; don't commit screenshots.
