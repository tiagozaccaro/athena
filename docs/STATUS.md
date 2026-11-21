# Athena status

_Shared handoff log for every coding agent. Update it at the end of each session (see AGENTS.md → Handoff)._

**Current milestone:** M8, automation (cron and webhook triggers, MCP server, Automation UI): parts A–D shipped in #114. M7 (the AI assistant, §4.5) is done except part D stage 3 (see **Next**).

Finished work is in `docs/HISTORY.md` (read it only when needed). When you finish something, add a bullet there with the PR number and remove it below.

## In progress

- HTTPS (`docs/specs/https.md`): all 4 parts done (#192, #196, #199, #203). Not verified: real Let's Encrypt or Cloudflare, trusting the CA on real devices. The last renewal/error live in memory only (a restart forgets them). Follow-up: own-certificate upload.
- Settings file (`docs/specs/settings-file.md`): part 1 in review; next, part 2.
- M7 D stage 2 follow-up ideas: show a delegate's own tool calls nested under its row; a Settings → AI page to see and clear notes and to list or upload skills; warn in the UI when Ollama runs a model with a context too small for Athena's prompt and tools (see `docs/agents/gotchas/assistant.md`); on a phone, a waiting question card sits mostly below the plan bar and prompt until you scroll.
- Dashboard follow-ups: touch dragging on a real phone; an app "update available" badge (`AppOut` has no such field).
- A webhook app restart once took 10 min and `GET /api/automation/jobs` hung meanwhile (Colima slow; rerun 10 s): does a run block the DB?
- E2E `install + smoke (windows-latest)` fails about half the time on main too: `500 GET /api/containers` during the phone/dark step (seen 2026-11-21). Find the server traceback in that job's log.
- Fix the ESLint config: `pnpm lint` skips `apps/web` `.tsx` (gotchas/web.md).
- Not yet verified for real: the Windows terminal (ConPTY plus PowerShell) beyond CI's pty tests, and the container shell through Docker in WSL.
- Not yet verified for real: the other Linux system managers' install/uninstall (dnf, pacman, zypper, apk; apt was checked in a Lima VM, see #26 in HISTORY) and every Windows manager (hand-written fixtures; CI runs choco/winget reads on Windows).
- Not yet verified in a browser: `/files/smb` (#104), the compose variant picker (#109), and the cloud wizard (#97) and remote cards (#92) with a real rclone remote.
- Catalog smoke test (#169, #172, fixes #173–#176): every store app was installed for real on macOS arm64 (Colima); 135/199 passed at first, the rest were fixed or honestly marked `smoke: skip` (GPU, accounts, 12–16 GB RAM: ragflow, indextts). Next: run the `Catalog smoke` workflow by hand for `--all` on amd64 and arm64 and fix what fails there. Logins and real use of each app aren't verified.
- Tunnel follow-ups (#150):
  - ngrok service files still hold a literal `${NGROK_AUTHTOKEN}` placeholder, so auto-start can't authenticate. <!-- docs-check: ignore -->
  - `tunnel_auto_start` is saved but nothing reads it at startup, so the tunnel doesn't start on boot.
  - Real-tested: a Cloudflare quick tunnel (macOS). Not yet: named tunnels, ngrok, Tailscale, Windows; service files need `/etc/cloudflared/config.yml`, which nothing writes.
  - Every tunnel detector (`platform/detect.py`) returns the action `"configure"`, which `Capability.actions` doesn't allow, so detection fails (logged as an error) on any host where cloudflared, ngrok or tailscale is installed. Add `configure` to `Action` (and regenerate the API client) or drop it.

- models.dev providers left out because pydantic-ai needs their own SDK: Google Vertex (service-account form for `GoogleProvider(vertexai=True)`), watsonx, GitLab, SAP AI Core and a few gateways. Vertex is the one worth adding.

- Only Ollama is detected on the host; other local AI servers (vLLM, llama.cpp...) are picked by hand. A detector per port, like `ai.ollama`, could offer "Use vLLM on this server".

## Next

M7 part D stage 3 (design §4.5 Parts): extras with outside services.
- Browser (#89): **blocked**. `pydantic-ai-harness[browser-use]==0.68.0` pins `browser-use` → `google-genai==1.65.0`, which conflicts with `pydantic-ai-slim[google]>=2.68.0` (`google-genai>=2.30.0`). Needs a harness release whose `browser-use` extra allows `google-genai>=2.30.0`; then unpin `pydantic-ai-harness` in `apps/server/pyproject.toml`. The toggle does nothing until then.
- Durable execution (D.6): turns run inside pgtask tasks against Postgres when `durable_execution_enabled` is on and `ATHENA_DURABLE_EXECUTION_DATABASE_URL` is set, checkpointing each model request and tool call; without them turns run inline as before. A real Postgres connection is tested; a crash/kill/resume flow isn't yet.
- Coding stack (D.7): foundation, file write/edit behind approval cards, shell behind `ShellGuard`, and Code Mode are done (see HISTORY). `Coder` from pydantic-ai-harness is intentionally not used: its bundled shell is unrestricted and bypasses `ShellGuard`. Deferred to later stages: `ipython_code_mode`, `smart_search`, `macroscope`, `capability_creation`, `pydantic_ai_docs`.

Raspberry Pi fixes and features from the competitor review: `docs/plans/improvements.md` (phase 1 fixes broken things: cloudflared download, store apps by host arch, broken catalog images, 32-bit install check, arm64 CI).

Later ideas (no milestone yet) are in `docs/design/milestones.md` → Backlog.

## Open questions

- `apps/server/pyproject.toml` installs the `coder` extra of pydantic-ai-harness, but `assistant/coding_stack.py` (and §4.5) say `Coder` isn't used (its shell bypasses `ShellGuard`). Drop the extra, or say why it stays?



## Blockers

- None. The first release (release-please PR #3, `RELEASE_PLEASE_TOKEN` is set) is on hold: the maintainer merges it once the plan under **Next** is complete. Agents: don't merge it or turn on its auto-merge.
