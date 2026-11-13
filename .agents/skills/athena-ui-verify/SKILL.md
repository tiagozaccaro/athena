---
name: athena-ui-verify
description: Verifies an Athena UI or API change end to end in a real browser before calling it done. It builds and serves the release version on a spare port with a fresh data dir, signs in, exercises the feature with Playwright MCP (snapshots, clicks, console and network checks, phone width, dark mode), checks side effects outside the browser, and cleans up. Use after changing anything under apps/web, any API the UI calls, or any feature that touches containers, apps, the store or files, and whenever asked to test, verify, screenshot or check the app.
---

# Verify Athena changes in a real browser

Unit tests prove the parts work. This proves the feature works for a person using it. Do every step; don't report a UI change as done without it.

The browser comes from the **`playwright` MCP server** (`.mcp.json`; headless, in-memory profile, screenshots in `.playwright-mcp/`). Claude's desktop browser pane works the same way when available. The tools you need:

| Need | Playwright MCP tool |
|---|---|
| Open a page | `browser_navigate` |
| Read the page (buttons, fields, text) to act on | `browser_snapshot` (prefer this over screenshots) |
| See the layout | `browser_take_screenshot` |
| Act | `browser_click`, `browser_type`, `browser_fill_form`, `browser_press_key`, `browser_select_option` |
| Catch errors | `browser_console_messages` |
| Prove what was sent | `browser_network_requests` |
| Phone width / dark mode | `browser_resize`, or `browser_evaluate` to toggle the `dark` class |

## 1. Build and serve the release version

Test what users get: the static export served by FastAPI, not `next dev`.

```bash
pnpm build
DATA=$(mktemp -d)/athena-data           # fresh data dir: first-run state
cd apps/server && ATHENA_WEB_DIR=../web/out uv run athena serve --port 8421 --data-dir "$DATA"
```

- Run the server in the background, and wait for `curl -sf localhost:8421/api/health`.
- Use **port 8421** (or any spare one), never 8420. The developer may already be running Athena there.
- After changing server code or catalog files, restart the server; it doesn't reload them.

## 2. Sign in

Create the admin through the API, then sign in through the UI. Use a throwaway test password, never a real one.

```bash
curl -s -H 'content-type: application/json' \
  -d '{"username":"admin","password":"test-pass-1234"}' localhost:8421/api/auth/setup
```

To exercise `/setup` or `/login` themselves, skip the curl and use the pages.

For API-only checks, keep a cookie jar and send the CSRF token on writes:

```bash
CSRF=$(curl -s -c jar -H 'content-type: application/json' \
  -d '{"username":"admin","password":"test-pass-1234"}' localhost:8421/api/auth/login \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['csrf_token'])")
curl -s -b jar -X POST -H "X-CSRF-Token: $CSRF" localhost:8421/api/...
```

## 3. Exercise the feature like a user

1. `browser_navigate` to the page, then `browser_snapshot` and `browser_take_screenshot`.
2. Use the feature through the UI: the happy path **and** at least one failure (bad input, a 409, a stopped runtime). Errors must show next to the field or in a toast or dialog, never silently.
3. After each action:
   - `browser_console_messages`: there must be no errors from this run. Errors from earlier servers in the same tab don't count; reload to be sure.
   - `browser_network_requests`: the request carried what the UI claimed (query params, body, status). This is how you catch a click that "worked" but sent the wrong value.
4. Long operations (deploy, refresh, runtime start) stream a job dialog. Wait for it to finish, then read its final status and lines.
5. Check the layout at **phone width** (`browser_resize` 375x812) and in **dark mode**. Look for no horizontal scroll, readable contrast, and nothing hidden.

Clicking tips:
- Base UI checkboxes and switches render a hidden `<input>` next to the visible control. Click the visible element, then confirm the state in a fresh snapshot.
- Positions change after dialogs close or the layout shifts. Take a new snapshot before clicking.

## 4. Check side effects outside the browser

The UI saying "done" isn't proof. Verify the real effect:

- **Apps:** `curl` the published port (expect 200); `ls -la <data>/apps/<name>` (files, `.env` mode `-rw-------`); `docker ps -a`.
- **Audit:** `sqlite3 <data>/athena.db "select action,target,detail from audit_log"`, or the same via Python.
- **Files written by the feature:** read them back.

## 5. Safety rules (non-negotiable)

- Never start, stop, remove or edit **containers, apps or volumes you didn't create**. The developer's own containers run on the same engine. Name everything you create `athena-demo-*` or `athena-test-*`, and act only on those.
- Before running anything that would change the host's runtime (`colima start`, stopping the engine, creating VMs), **fake it**:
  - put a stub script first on the server's `PATH`; or
  - point `HOME` at an empty directory so a runtime looks stopped.
  - Confirm the stub is what will run (`ps eww -p <pid>`) before clicking.
- Prefer images from registries other than Docker Hub for test installs (codeberg.org, ghcr.io). Anonymous Docker Hub pulls are rate-limited, and `docker manifest inspect` loops burn the quota.
- Don't use real credentials anywhere. Test passwords only.

## 6. Clean up and report

- Remove what you created (`DELETE /api/apps/<name>?delete_data=true` or the UI), check `docker ps -a` shows only what was there before, and check that no test networks are left (`docker network ls`).
- Stop the server and delete the temporary data dir and `.playwright-mcp/` screenshots.
- Report what you verified, what you couldn't (and why), and any bugs found and fixed along the way. Record notable findings in `docs/STATUS.md`.
