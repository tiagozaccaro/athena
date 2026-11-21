# Athena built-in catalog

Apps offered in Athena's store (about 200). Each app is a folder with a `compose.yaml`, plus optional variant files (see [Variants](#variants)):

```
apps/<id>/compose.yaml
apps/<id>/compose.<slug>.yaml   # optional variants
```

`<id>` is lowercase letters, digits and dashes. The file is a normal Docker Compose file with an `x-athena` block describing the app and its install form:

```yaml
x-athena:
  title: Jellyfin
  description: Stream your movies, shows and music to any device.
  category: media        # ai, media, files, productivity, notes, documents, reading,
                         # finance, development, databases, home, network, security,
                         # monitoring, downloads, utilities
  icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/jellyfin.svg
  homepage: https://jellyfin.org
  web_port: WEB_PORT     # env key (or a number) that the "Open" button uses
  platforms: [linux/amd64, linux/arm64]  # CPUs its images exist for; filled by a script
  notes: >-              # optional, shown on the store page
    First-run instructions.
  tagline: Your own streaming service for movies, shows and music.  # card subtitle
  tags: [Movies, TV, Music]      # up to 6 small chips on the card
  license: GPL-2.0               # shown on the app page
  popular: true                  # featured in the store's front-page carousel
  smoke: web                     # what the runtime smoke test checks: web (default),
                                 # start (no reachable web page) or skip
  smoke_note: needs an NVIDIA GPU  # why smoke isn't web
  features:                      # up to 8 bullets, "What you get" on the app page
    - Stream to TVs, phones, browsers and DLNA devices
    - Hardware transcoding when the host supports it
  screenshots:                   # up to 6 http(s) URLs; the first is the card cover
    - https://example.com/screenshot.png
  env:                   # one form field per entry; answers are written to .env
    - key: WEB_PORT
      label: Web port
      type: port         # text, password, port, path, number, boolean, select
      default: "8096"
      description: Port the web UI listens on on this server.  # optional help text under the field
    - key: DB_TYPE
      label: Database
      type: select
      options: [sqlite, mysql]  # required for type: select (non-empty)
      default: sqlite
    - key: MEDIA_PATH
      label: Media folder
      type: path
      default: "@app_data/media"
    - key: TZ
      label: Timezone
      default: "@timezone"
      advanced: true     # collapsed under "Advanced" in the form
    - key: DB_PASSWORD
      label: Database password
      type: password
      generate: secret   # random value when left empty (32 URL-safe characters);
                         # hex16 / hex32 for keys an app decodes as hex (32 / 64 characters)
    - key: SMTP_HOST
      label: Mail server
      required: false    # default true: an empty value is refused unless generated

services:
  jellyfin:
    image: jellyfin/jellyfin:10.10
    ports: ["${WEB_PORT}:8096"]
    volumes:
      - ${ATHENA_APP_DATA}/config:/config
      - ${MEDIA_PATH}:/media:ro
```

### Variants

An app folder may hold several compose files: `compose.yaml` is the default variant and
each `compose.<slug>.yaml` sibling is another installable variant of the same app
(e.g. `compose.postgres.yaml`). Every variant file is a complete x-athena compose doc
with its own `env` form fields; the store lists them as a variant picker on the app's
install page, and the chosen variant's compose file is deployed. App-level metadata
(title, category, icon, …) comes from `compose.yaml`. The picker's name is
`x-athena.variant.label` in the variant file (`variant: {label: PostgreSQL}`), or the
slug title-cased when it's missing.

## Rules

- **Standard interpolation only.** Reference form values as `${KEY}`. Every `${…}` must be a declared `env` key or `ATHENA_APP_DATA`, which is the app's own data folder on the server. Athena writes the answers to `.env` next to `compose.yaml`, so the file works with plain `docker compose` too.
- **Default tokens:**
  - `@timezone` is the host's timezone.
  - `@uid` and `@gid` are the server user's IDs (1000 when Athena runs as root).
  - `@app_data` and `@app_data/<sub>` are paths inside the app's data folder.
- **Pin image tags** to a release, a major version, or an official channel (`stable`). Check that they exist for `linux/amd64` and `linux/arm64`.
- **`platforms`** lists the CPUs every image of the default `compose.yaml` is published for (`linux/amd64`, `linux/arm64`, `linux/arm/v7`). Don't write it by hand: `cd apps/server && uv run python -m athena.catalog.image_platforms <id> --write` reads the registries and sets it (no ids: every app; no `--write`: report only). The store hides apps that don't match the host's CPU, marks amd64-only apps on an arm64 Mac or Windows PC as "Emulated", and install refuses the rest. Run it once at a time: Docker Hub's tag API allows about 180 requests a minute and a full run uses about 140.
- **No fixed secrets.** Never ship a password, key or token as a literal (CasaOS files often do). Make it a `type: password` field with `generate: secret` (or `hex16`/`hex32`), and use the same `${KEY}` everywhere the value appears (a database URL, a `--requirepass` argument). Gitleaks fails the commit otherwise.
- **Open-source apps only.** Use web ports that don't clash with other catalog apps, so several apps can run side by side.
- **Icons** come from [dashboard-icons](https://github.com/homarr-labs/dashboard-icons) (Apache-2.0).
- **Screenshots** should come from the project's own repository or documentation site (a raw GitHub URL is fine). Keep them under a few hundred KB, and check that the URL answers 200. The store falls back to the app icon when a screenshot can't load, so a missing or rotted URL is not fatal.
- **`tagline`, `tags`, `features`, `license` and `popular`** are optional but make the store page useful. `popular: true` puts the app in the front-page carousel (it autoplays), so use it for the handful of apps a home server actually starts with.

## Checks

`apps/server/tests/test_catalog.py` loads every app, checks its metadata and variables, and fills the form with defaults. When a container engine is available (`ATHENA_DOCKER_TESTS=1`, which is on in Linux CI), it also runs `docker compose config` on each app. Every app must declare `platforms` (except those in `UNREADABLE`, whose images can't be read yet); `ATHENA_NETWORK_TESTS=1` also checks them against the registries.

`python -m athena.catalog.smoke` installs apps for real and checks they come up: it fills the form with defaults (ports moved to free ones, paths into a temporary folder), pulls the images, runs `compose up` under an `athena-test-<id>` project, and waits until the web port answers with a status below 500 (or, with `smoke: start`, until the containers keep running for 30 s). Then it takes the app down with its volumes and removes the images it pulled. Apps whose images don't run on the host's CPU are skipped.

```bash
cd apps/server
uv run python -m athena.catalog.smoke <id> [<id>…]   # some apps
uv run python -m athena.catalog.smoke --changed      # apps changed against origin/main, uncommitted included
uv run python -m athena.catalog.smoke --all --jobs 3 # every app: hours and many GB of downloads
```

Other flags: `--variants` (every compose variant), `--timeout` (seconds, default 180, doubled for emulated apps), `--keep` (leave the app running to inspect it), `--keep-images`, `--min-free-gb` (stop starting apps below this much free disk, default 20; on Colima it also runs `fstrim` in the VM after each app), `--shard K/N`, `--out` (default `catalog-smoke-report/`, with `summary.md`, `results.json` and `logs/<id>.log` for each failure). Use `smoke: start` for apps without a web page reachable from the host (host networking is detected on its own) and `smoke: skip` with a `smoke_note` for apps that can't run on a test machine (a GPU, a device, a required account token). <!-- docs-check: ignore -->

The `Catalog smoke` workflow runs it on amd64 and arm64 Linux: on pull requests for the apps they change, weekly and by hand for every app (split into shards), or by hand for named apps.

The catalog is bundled into the server wheel as `athena/catalog_builtin`.
