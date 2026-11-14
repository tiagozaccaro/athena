---
name: athena-catalog-app
description: Adds or updates an app in Athena's built-in store (catalog/apps/<id>/compose.yaml with x-athena metadata) - choosing and checking image tags, ports, the install form, icons and licenses, then validating it. Use when asked to add, update, fix or bump an app in the store or catalog, or when tests/test_catalog.py fails.
---

# Add or update a catalog app

The format is in `catalog/README.md`. Read it first; this skill is the process around it.

## 1. Check the app qualifies

- **Open source.** Check the upstream repo's LICENSE. Don't add apps under non-commercial or "source available" licenses (that's why Umbrel's store isn't used).
- **Multi-arch.** The image must exist for `linux/amd64` and `linux/arm64`. Most home servers are a NAS or a Raspberry Pi.
- **Not already there:** `ls catalog/apps`.

## 2. Pick the image tag without burning Docker Hub's rate limit

Anonymous Docker Hub pulls and manifest lookups are rate-limited. A loop of `docker manifest inspect` once locked out installs for hours.

- Pin to a release, a major version or an official channel (`10.10`, `v0.107.65`, `stable`). Never `latest`.
- Find the tag from the upstream release notes or the registry's web API, one request per image:
  - Docker Hub: `curl -s "https://hub.docker.com/v2/repositories/<ns>/<repo>/tags/<tag>" | jq '{name, archs: [.images[]?.architecture] | unique}'`. A missing tag returns an error object instead of `name`.
  - GHCR: the package page `https://github.com/<owner>/<repo>/pkgs/container/<name>`.
- If both an upstream GHCR image and a Docker Hub one exist, prefer GHCR.

## 3. Write `catalog/apps/<id>/compose.yaml`

Start from a similar app in `catalog/apps/` (a web app with a database, e.g. `nextcloud` or `paperless-ngx`; a single container, e.g. `it-tools`).

Checklist:
- `<id>`: lowercase letters, digits and dashes. It's the folder name.
- `x-athena`:
  - `title`, a one-line `description`, a `category` from the README list, and `homepage`.
  - `icon`: `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/<name>.svg`. Open the URL to check it exists (`curl -sI ... | head -1` should say 200). Use `png/` if there's no SVG.
  - `web_port: WEB_PORT`, and a `WEB_PORT` field whose default no other catalog app uses (`grep -rh -A3 'key: WEB_PORT' catalog/apps | grep default` lists the taken ones).
  - `notes` for anything the user must do on first run (default credentials, a port 53 clash, a setup wizard).
- **Every `${VAR}`** is a declared `env` key or `ATHENA_APP_DATA`. Defaults use `@timezone`, `@uid`, `@gid` or `@app_data/<sub>`. Passwords and secrets use `type: password` plus `generate: secret`.
- **Data** lives under `${ATHENA_APP_DATA}/<sub>`. User media goes through a `type: path` field.
- Add `restart: unless-stopped` on long-running services.
- **YAML 1.2:** quote anything that looks like a boolean or a number (`"yes"`, `"8080"`, `"0755"`).

## 4. Validate

```bash
cd apps/server
uv run pytest -q tests/test_catalog.py                     # loads every app, checks metadata, variables and ports
ATHENA_DOCKER_TESTS=1 uv run pytest -q tests/test_catalog.py -k compose   # docker compose config on each app (needs an engine)
```

Then install it once for real through the UI, following the `athena-ui-verify` skill:
- Open the store page, then install with defaults into a fresh data dir.
- Check that the "Open" button reaches the web UI (`curl -s -o /dev/null -w '%{http_code}' localhost:<port>`).
- Remove it with "delete data".

Name a test install `athena-demo-<id>` if the form allows it, and act only on what you created. A server restart is needed to pick up catalog changes.

## 5. Ship

- Use one PR per app, or one for a batch of tag bumps, with a title like `feat(catalog): add <app>` or `fix(catalog): bump <app> to <tag>`. Follow the `athena-ship` skill.
- The built-in catalog has no licensing row of its own in §9, but if an app's license is unusual, say so in the PR body.
