# Athena built-in catalog

Apps offered in Athena's store. Each app is a folder with one file:

```
apps/<id>/compose.yaml
```

`<id>` is lowercase letters, digits and dashes. The file is a normal Docker Compose file with an `x-athena` block describing the app and its install form:

```yaml
x-athena:
  title: Jellyfin
  description: Stream your movies, shows and music to any device.
  category: media        # media, files, productivity, development, home, network,
                         # security, monitoring, downloads, utilities
  icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/jellyfin.svg
  homepage: https://jellyfin.org
  web_port: WEB_PORT     # env key (or a number) that the "Open" button uses
  notes: >-              # optional, shown on the store page
    First-run instructions.
  env:                   # one form field per entry; answers are written to .env
    - key: WEB_PORT
      label: Web port
      type: port         # text, password, port, path, number, boolean, select
      default: "8096"
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
      generate: secret   # random value when left empty

services:
  jellyfin:
    image: jellyfin/jellyfin:10.10
    ports: ["${WEB_PORT}:8096"]
    volumes:
      - ${ATHENA_APP_DATA}/config:/config
      - ${MEDIA_PATH}:/media:ro
```

## Rules

- **Standard interpolation only.** Reference form values as `${KEY}`. Every `${…}` must be a declared `env` key or `ATHENA_APP_DATA`, which is the app's own data folder on the server. Athena writes the answers to `.env` next to `compose.yaml`, so the file works with plain `docker compose` too.
- **Default tokens:**
  - `@timezone` is the host's timezone.
  - `@uid` and `@gid` are the server user's IDs (1000 when Athena runs as root).
  - `@app_data` and `@app_data/<sub>` are paths inside the app's data folder.
- **Pin image tags** to a release, a major version, or an official channel (`stable`). Check that they exist for `linux/amd64` and `linux/arm64`.
- **Open-source apps only.** Use web ports that don't clash with other catalog apps, so several apps can run side by side.
- **Icons** come from [dashboard-icons](https://github.com/homarr-labs/dashboard-icons) (Apache-2.0).

## Checks

`apps/server/tests/test_catalog.py` loads every app, checks its metadata and variables, and fills the form with defaults. When a container engine is available (`ATHENA_DOCKER_TESTS=1`, which is on in Linux CI), it also runs `docker compose config` on each app.

The catalog is bundled into the server wheel as `athena/catalog_builtin`.
