---
name: athena-ship
description: Takes an Athena change from "code written" to "merged" - branch, local checks, commit, PR with auto-merge, CI and CodeQL watching, fixing failures, and the STATUS handoff. Use whenever you are about to commit, push, open or update a pull request, when asked to "check" a PR or CI, when a check failed, or when finishing a task or session.
---

# Ship an Athena change

Follow these steps in order. Each step says what "done" looks like. Don't skip one because the change looks small; docs-only PRs still need the title check and auto-merge.

## 1. Be on the right branch

```bash
git status -sb          # where am I, is anything uncommitted?
```

- On `main`, or on a branch for a different task: start a new branch from an up-to-date `main`:
  `git switch main && git pull && git switch -c <type>/<short-description>`
- **The checkout has someone else's uncommitted work** (another agent session may be using it): don't switch branches under it. Use a worktree:
  `git fetch origin && git worktree add ../athena-<topic> -b <type>/<topic> origin/main`, then work in `../athena-<topic>`. Remove it after the merge: `git worktree remove ../athena-<topic>`.
- Types: `feat`, `fix`, `perf`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`, `revert`.

## 2. Run the local checks

```bash
scripts/check.sh            # what CI runs: repo, web (lint, types, build, API client drift), server (ruff, pytest)
scripts/check.sh --quick    # same without the web build, while iterating
```

Done when it prints "All checks passed". If it regenerated `packages/api-client`, commit those files.

If `git config core.hooksPath` doesn't print `.githooks`, run `git config core.hooksPath .githooks` so the pre-push hook runs these checks on every push.

If the docs check fails, you renamed or removed something that AGENTS.md, AGENT-NOTES or a skill still names. Fix the doc in the same commit; don't silence it.

Also, depending on what changed:
- **Anything in `apps/web`, or an API the UI uses:** browser verification with the `athena-ui-verify` skill. This is required before saying "done".
- **A database model:** a new migration (see the `athena-recipes` skill). `tests/test_db.py` fails without one.
- **A new dependency:** add its license to `docs/mvp-design.md` §9. Open-source only.
- **A design change:** update the `docs/mvp-design.md` section and add a row to §11.

## 3. Commit

- Use Conventional Commit messages (`feat(files): add folder upload`), and explain _why_ in the body.
- Don't touch `CHANGELOG.md` or `version.txt`.
- Never commit to `main`, and never force-push (it's blocked). To bring in `main`: `git merge origin/main`, not a rebase.
- Merge conflict in `packages/api-client/*`: don't hand-merge it. Take either side, run `pnpm gen:api`, and commit. Search for leftover markers before committing: `git grep -n '^<<<<<<< '`.

## 4. Open the PR and turn on auto-merge

```bash
git push -u origin HEAD
gh pr create --title "<type>(<scope>): <summary>" --body "<what, why, how it was verified, what wasn't>"
gh pr merge <n> --squash --auto --delete-branch      # always, without asking
```

- The title becomes the squash commit and the changelog line, so make it Conventional and specific.
- In the body, state what was verified and how (tests, browser, real host), and what wasn't verified. End it with the attribution line your tool requires, if any.
- Auto-merge exceptions: release-please PRs (the maintainer merges those), and PRs whose base isn't `main`. Turn it on for those only after GitHub retargets them to `main`.

## 5. Watch CI until it's green

```bash
gh pr checks <n>                                   # summary; re-run until nothing is pending
gh run view <run-id> --log-failed | tail -80       # the failing step's output
gh api 'repos/tiagozaccaro/athena/code-scanning/alerts?state=open&ref=refs/pull/<n>/merge' \
  --jq '.[] | "\(.rule.id) \(.most_recent_instance.location.path):\(.most_recent_instance.location.start_line) \(.rule.description)"'
gh pr view <n> --json state,mergeStateStatus,mergedAt
```

Triage table:

| Symptom | Likely cause | Action |
|---|---|---|
| Only `server (windows-latest)` fails | Paths, encoding, CRLF, trailing dots | See AGENT-NOTES "Windows portability"; fix and push |
| Only `server (macos-latest)` fails | A CLI missing on the runner (e.g. no `docker`) | Make the test really hide or stub the tool |
| A job was **cancelled**, not failed | macOS runner capacity | `gh run rerun <run-id> --failed` |
| `web` fails at "API client is up to date" | You changed the API without regenerating | `pnpm gen:api`, commit |
| `install script (windows-latest)` lint | PSScriptAnalyzer | You can't run it locally without pwsh; read the log and fix exactly what it names |
| CodeQL fails | A code scanning alert | Fix it in code (AGENT-NOTES "CodeQL" lists the known false-positive shapes). Don't dismiss alerts; that's the maintainer's call |
| `pr-title` fails | Title isn't `type(scope): summary` | `gh pr edit <n> --title "..."` |
| Merge state `BEHIND` / `DIRTY` | `main` moved (often STATUS.md) | `git merge origin/main`, resolve, push |

Done when `gh pr view` says `MERGED`. Auto-merge waits only for the required checks (`ci-ok`, `pr-title`), so make sure CodeQL is green too. Never say "merged" without checking.

## 6. Hand off

Before ending the session, on the branch (or in a follow-up docs PR):
- `docs/STATUS.md`: move finished items to Done with the PR number. Under In progress, say exactly where you stopped and the next concrete step.
- `docs/AGENT-NOTES.md`: add anything non-obvious you learned (a surprising failure, a tool quirk, a pattern).
- Report to the maintainer: what merged (with links), what's still running, what was verified and what wasn't, and the bugs fixed along the way.
