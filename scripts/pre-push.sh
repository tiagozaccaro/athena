#!/usr/bin/env bash
# Git pre-push hook: runs the parts of scripts/check.sh that the pushed commits touch,
# so a push that would fail CI stops here instead of minutes later.
#
# Enable once per clone (works for every agent and for people):
#   git config core.hooksPath .githooks
# Skip once:   git push --no-verify      (or ATHENA_SKIP_CHECKS=1 git push)
# Disable:     git config --unset core.hooksPath
#
# Git passes "<local ref> <local sha> <remote ref> <remote sha>" lines on stdin.
set -uo pipefail

if [ "${ATHENA_SKIP_CHECKS:-0}" = 1 ]; then
  echo "pre-push: ATHENA_SKIP_CHECKS=1, skipping checks"
  exit 0
fi

cd "$(git rev-parse --show-toplevel)" || exit 1
ZERO=0000000000000000000000000000000000000000

changed=""
while read -r _local_ref local_sha _remote_ref remote_sha; do
  [ "$local_sha" = "$ZERO" ] && continue # deleting a remote branch
  if [ "$remote_sha" != "$ZERO" ] && git cat-file -e "$remote_sha" 2>/dev/null; then
    base="$remote_sha"
  else
    base=$(git merge-base "$local_sha" origin/main 2>/dev/null || true)
  fi
  if [ -n "$base" ]; then
    changed+=$(git diff --name-only "$base" "$local_sha")$'\n'
  else
    changed+=$'apps/server/\napps/web/\n' # unknown history: check everything
  fi
done

[ -z "${changed//$'\n'/}" ] && exit 0

parts=(repo)
if grep -qE '^(apps/server/|packages/api-client/)' <<<"$changed"; then
  parts+=(server web) # an API change can leave the generated client stale
elif grep -qE '^(apps/web/|packages/|package\.json|pnpm-)' <<<"$changed"; then
  parts+=(web)
fi

echo "pre-push: running scripts/check.sh --quick ${parts[*]} (skip with git push --no-verify)"
exec scripts/check.sh --quick "${parts[@]}"
