# athena-server

The Athena backend: a FastAPI app, packaged as `athena-server`, that serves the API and the built web UI.

## Development

```bash
uv sync
uv run athena serve --reload        # API on http://localhost:8420
uv run pytest
uv run ruff check && uv run ruff format --check
```

Run the web app at the same time with `pnpm dev` from the repo root. It proxies `/api` to this server.

## CLI

| Command | What it does |
|---|---|
| `athena serve [--host --port --data-dir --reload]` | Run the server |
| `athena openapi [--output FILE]` | Print or write the OpenAPI schema, which `packages/api-client` is generated from |
| `athena service install --data-dir DIR --port N [--dry-run]` | Register Athena to start automatically: systemd (Linux, root), launchd agent (macOS), Scheduled Task at logon (Windows) |
| `athena service uninstall [--dry-run]` | Remove that registration |
| `athena service status` | Show whether the service is registered and running |

The install scripts in `scripts/` call `athena service install` after installing the wheel.
