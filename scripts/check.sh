#!/usr/bin/env bash
# Runs the same checks as CI (.github/workflows/ci.yml) on this machine, so you know
# before pushing whether `ci-ok` will pass. Run from anywhere inside the repo.
#
#   scripts/check.sh            everything (repo, web, server)
#   scripts/check.sh --quick    skip the web build (the slowest step)
#   scripts/check.sh web        only the web checks (also: server, repo)
#
# What CI runs that this can't: the other two operating systems. Windows-only failures
# (paths, CRLF, PowerShell lint without pwsh) still show up only in CI. See
# docs/AGENT-NOTES.md -> Windows portability.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

QUICK=0
PARTS=()
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    web | server | repo) PARTS+=("$arg") ;;
    -h | --help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg (see --help)" >&2; exit 2 ;;
  esac
done
[ ${#PARTS[@]} -eq 0 ] && PARTS=(repo web server)

FAILED=()
SKIPPED=()

step() { # step <name> <command...>
  local name="$1"
  shift
  printf '\n\033[1m== %s\033[0m\n' "$name"
  if "$@"; then
    printf '\033[32mok\033[0m  %s\n' "$name"
  else
    printf '\033[31mFAIL\033[0m %s\n' "$name"
    FAILED+=("$name")
  fi
}

skip() { # skip <name> <reason>
  printf '\n\033[33mskip\033[0m %s (%s)\n' "$1" "$2"
  SKIPPED+=("$1")
}

api_client_up_to_date() {
  local before after
  before=$(git diff -- packages/api-client | git hash-object --stdin)
  pnpm gen:api >/dev/null || return 1
  after=$(git diff -- packages/api-client | git hash-object --stdin)
  if [ "$before" != "$after" ]; then
    echo "packages/api-client was out of date. It has been regenerated; commit the result."
    return 1
  fi
}

has() { command -v "$1" >/dev/null 2>&1; }

for part in "${PARTS[@]}"; do
  case "$part" in
    repo)
      step "agent config in sync (.mcp.json -> opencode.json)" node scripts/agents-sync.mjs --check
      step ".claude/skills points at .agents/skills" test "$(readlink .claude/skills)" = "../.agents/skills"
      if has shellcheck; then step "shellcheck" shellcheck scripts/*.sh; else skip "shellcheck" "not installed"; fi
      if has actionlint; then step "actionlint" actionlint; else skip "actionlint" "not installed"; fi
      if has pwsh; then
        # shellcheck disable=SC2016 # PowerShell code: $i must reach pwsh unexpanded.
        step "PSScriptAnalyzer" pwsh -NoProfile -Command \
          'if (-not (Get-Module -ListAvailable PSScriptAnalyzer)) { Install-Module PSScriptAnalyzer -Force -Scope CurrentUser }; $i = Invoke-ScriptAnalyzer -Path scripts/install.ps1 -Severity Warning,Error; $i | Format-Table -AutoSize; if ($i) { exit 1 }'
      else
        skip "PSScriptAnalyzer" "pwsh not installed; CI's Windows job is the first check"
      fi
      step "install.sh dry run" bash -c 'bash scripts/install.sh --dry-run --version 0.0.0 >/dev/null && bash scripts/install.sh --dry-run --uninstall --purge >/dev/null'
      ;;
    web)
      [ -d node_modules ] || step "pnpm install" pnpm install --frozen-lockfile
      step "API client up to date (pnpm gen:api)" api_client_up_to_date
      step "web lint" pnpm lint
      step "web typecheck" pnpm typecheck
      if [ "$QUICK" = 1 ]; then skip "web build" "--quick"; else step "web build (static export)" pnpm build; fi
      ;;
    server)
      step "ruff check" bash -c 'cd apps/server && uv run ruff check'
      step "ruff format --check" bash -c 'cd apps/server && uv run ruff format --check'
      step "pytest" bash -c 'cd apps/server && uv run pytest -q'
      step "service install dry run" bash -c 'cd apps/server && uv run athena service install --dry-run >/dev/null'
      ;;
  esac
done

echo
if [ ${#SKIPPED[@]} -gt 0 ]; then echo "Skipped: ${SKIPPED[*]}"; fi
if [ ${#FAILED[@]} -gt 0 ]; then
  printf '\033[31mFailed (%d): %s\033[0m\n' "${#FAILED[@]}" "$(IFS=,; echo "${FAILED[*]}")"
  exit 1
fi
printf '\033[32mAll checks passed.\033[0m Windows and macOS-only issues still need CI.\n'
