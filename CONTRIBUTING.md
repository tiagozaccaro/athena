# Contributing to Athena

Thanks for helping out! This guide covers how changes get into Athena. Read [docs/mvp-design.md](docs/mvp-design.md) for the architecture and [docs/STATUS.md](docs/STATUS.md) for what's being worked on.

## Workflow

`main` is protected. Nobody pushes to it directly, maintainers included. Every change goes through a branch and a pull request.

1. **Branch from an up-to-date `main`:**
   ```bash
   git switch main && git pull
   git switch -c feat/app-store-install-form
   ```
   Branch names are `<type>/<short-description>`, using the same types as commits (below).
2. **Commit** in small, focused steps. Individual commit messages are free-form, because the PR is squashed.
3. **Open a pull request** against `main`. Use the template and fill in the testing section.
4. **CI must pass**, and all review conversations must be resolved.
5. **Squash-merge.** The PR title becomes the commit on `main`, and the branch is deleted automatically.

## PR titles: Conventional Commits

PR titles are checked by CI and drive versioning and the changelog:

```
<type>(<optional scope>): <description>
```

| Type | Use for | Version bump |
|---|---|---|
| `feat` | A new user-facing feature | minor |
| `fix` | A bug fix | patch |
| `perf` | A performance improvement | patch |
| `docs` | Documentation only | none |
| `refactor` | Code change that doesn't fix a bug or add a feature | none |
| `test` | Tests only | none |
| `build` | Build system or dependencies | none |
| `ci` | CI configuration | none |
| `chore` | Anything else | none |
| `revert` | Reverts a previous change | patch |

Common scopes: `web`, `ui`, `server`, `containers`, `packages`, `store`, `files`, `cloud`, `terminal`, `assistant`, `install`, `agents`.

Add `!` after the type (`feat!: …`) or a `BREAKING CHANGE:` footer for breaking changes.

## Releases

[release-please](https://github.com/googleapis/release-please) keeps a release PR open that collects merged changes. Merging that PR tags a version, publishes a GitHub release with the changelog, and attaches the install scripts and packages.

## Cross-platform rules

Athena runs on Linux, macOS and Windows. Any change that touches the host (containers, package managers, files, terminal, services) must:

- go through a platform provider and capability (see the `athena-platform-feature` skill in `.agents/skills/`);
- be tested on every OS it claims to support, either in CI or manually. List the OSes in the PR;
- use open-source dependencies only, recorded in [docs/mvp-design.md §9](docs/mvp-design.md#9-dependency--license-inventory).

## AI coding agents

AI-assisted contributions are welcome. Agents must follow [AGENTS.md](AGENTS.md), which covers the same workflow plus the shared skills, MCP servers and handoff notes in `docs/STATUS.md`.

## Code of conduct

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
