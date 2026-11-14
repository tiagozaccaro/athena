#!/usr/bin/env node
// Checks that the agent docs point at things that exist.
//
// Agents (weaker models especially) follow AGENTS.md, docs/AGENT-NOTES.md and the
// project skills literally, so a renamed file or function there sends them the wrong
// way. This script reads every `inline code` span in those docs and checks:
//   - paths (apps/server/..., scripts/check.sh, @workspace/ui/..., @/hooks/...) exist;
//   - code names (calls like run_or_fail(...), decorators like @pytest.mark.skipif,
//     components like <JobDialog>, snake_case, CamelCase, camelCase and CONSTANT_NAMES)
//     appear somewhere in the source code.
// Paths in fenced code blocks are checked too; names there aren't (they're examples).
//
// When a doc mentions something on purpose that doesn't exist (an old name, an
// external API, a "don't use X"), end that line with  <!-- docs-check: ignore -->
// or add the name to EXTERNAL below with a reason.
//
//   node scripts/check-docs.mjs          check
//   node scripts/check-docs.mjs --list   also print every name it verified
import { execFileSync } from "node:child_process"
import { existsSync, readFileSync, statSync } from "node:fs"
import { join } from "node:path"

const ROOT = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim()
process.chdir(ROOT)

// Names from libraries, the OS or other tools that docs may cite without the
// repo's code containing them.
const EXTERNAL = new Set([
  // Python stdlib / libraries
  "compare_digest", "shutil.which", "subprocess.Popen", "start_new_session", "TIOCSCTTY",
  "pty.fork", "ptyprocess", "PurePosixPath", "write_bytes", "ClassVar", "send2trash",
  "timeout_graceful_shutdown", "skipif", "pytest.mark.skipif", "server_default",
  "op.create_table", "op.add_column", "sa.Column", "urllib.parse", "GetFullPathNameW",
  "handle_delete", "handle_copy", "handle_move", "compare_metadata",
  // Web / React / Next / Base UI
  "useLayoutEffect", "setTheme", "useSearchParams", "skipTrailingSlashRedirect",
  "trailingSlash", "document.write", "asChild", "FieldGroup", "InputGroupInput",
  // GitHub / tooling
  "workflow_dispatch", "BasicAuthLevel", "mcp__ccd_pr__set_monitor", "LASTEXITCODE",
  "CONTEXT7_API_KEY", "RELEASE_PLEASE_TOKEN", "PSAvoidUsingWriteHost", "mount_webdav",
])
// Tool names of MCP servers (Playwright's browser_*, Claude's mcp__*).
const EXTERNAL_PREFIXES = ["browser_", "mcp__"]

const DOCS = [
  "AGENTS.md",
  "CLAUDE.md",
  "docs/AGENT-NOTES.md",
  "apps/web/AGENTS.md",
  "apps/server/AGENTS.md",
  "catalog/README.md",
  ...projectSkills(),
].filter((f) => existsSync(f))

const CODE_EXT = /\.(py|ts|tsx|mts|mjs|js|json|ya?ml|toml|sh|ps1|css|ini|cfg)$/
const FILE_EXT = /\.(py|tsx?|mjs|js|json|ya?ml|toml|sh|ps1|md|css|txt|lock|ini)$/
const IGNORE_LINE = "docs-check: ignore"

const tracked = git(["ls-files", "--cached", "--others", "--exclude-standard"])
const dirNames = new Set()
for (const f of tracked) {
  const parts = f.split("/")
  for (let i = 0; i < parts.length - 1; i++) dirNames.add(parts[i])
}

// Everything the code says, minus the docs being checked (so they can't vouch for
// themselves) and generated lockfiles.
const corpusFiles = tracked.filter(
  (f) => CODE_EXT.test(f) && !f.endsWith("pnpm-lock.yaml") && !f.endsWith("uv.lock") && !DOCS.includes(f)
)
const corpus = corpusFiles.map((f) => safeRead(f)).join("\n")
const words = new Set(corpus.match(/[A-Za-z_][A-Za-z0-9_]*/g))

const PATH_ROOTS = [
  "",
  "apps/server/src/athena/",
  "apps/server/src/",
  "apps/server/",
  "apps/web/",
  "packages/ui/src/",
  "packages/ui/src/components/",
]
const ALIASES = [
  ["@workspace/ui/", "packages/ui/src/"],
  ["@workspace/api-client", "packages/api-client"],
  ["@/", "apps/web/"],
]
const TRY_EXT = ["", ".ts", ".tsx", ".py", ".md", ".mjs", "/index.ts", "/SKILL.md"]

const problems = []
const verified = new Set()

for (const doc of DOCS) {
  const lines = readFileSync(doc, "utf8").split("\n")
  let fenced = false
  lines.forEach((line, i) => {
    if (/^\s*```/.test(line)) {
      fenced = !fenced
      return
    }
    if (line.includes(IGNORE_LINE)) return
    const where = `${doc}:${i + 1}`
    if (fenced) {
      for (const piece of line.split(/[\s"'=()]+/)) checkPath(piece, where, true)
      return
    }
    for (const m of line.matchAll(/`([^`]+)`/g)) checkSpan(m[1].trim(), where)
  })
}

if (process.argv.includes("--list")) console.log([...verified].sort().join("\n"))
if (problems.length) {
  console.error(`Docs name ${problems.length} thing(s) that don't exist:\n`)
  for (const p of problems) console.error(`  ${p}`)
  console.error(
    `\nFix the doc (or the code). If the mention is deliberate, end the line with <!-- ${IGNORE_LINE} -->` +
      " or add the name to EXTERNAL in scripts/check-docs.mjs."
  )
  process.exit(1)
}
console.log(`docs check: ${verified.size} paths and names in ${DOCS.length} files all exist.`)

// ---------------------------------------------------------------------------------

function checkSpan(span, where) {
  if (/:\/\/|^\$|^-/.test(span)) return
  // Commands and phrases: check each path-looking piece.
  if (/\s/.test(span)) {
    for (const piece of span.split(/[\s"'=]+/)) checkPath(piece, where, false)
    return
  }
  if (checkPath(span, where, false)) return
  checkName(span, where)
}

/** Returns true when the token was treated as a path (checked or skipped as one). */
function checkPath(raw, where, strict) {
  let p = raw.replace(/[.,;:)\]]+$/, "").replace(/:\d+(-\d+)?$/, "").replace(/#.*$/, "")
  if (!p || /[<>*{}$|~`\\]|:\/\//.test(p) || p.startsWith("/") || p.startsWith("-")) return false
  if (p.startsWith("../") || /^\.\w+$/.test(p) || p.includes(":")) return false
  let aliased = false
  for (const [from, to] of ALIASES) {
    if (p.startsWith(from)) {
      p = to + p.slice(from.length)
      aliased = true
      break
    }
  }
  const first = p.replace(/^\.\//, "").split("/")[0]
  const looksLikePath =
    aliased ||
    (p.includes("/") && (dirNames.has(first) || first.startsWith("."))) ||
    (!strict && FILE_EXT.test(p) && /^[\w.@/-]+$/.test(p) && !/^\d/.test(p))
  if (!looksLikePath) return false
  if (strict && !aliased && !(p.includes("/") && dirNames.has(first))) return false
  for (const root of PATH_ROOTS) {
    for (const ext of TRY_EXT) {
      if (existsSync(join(root, p + ext))) {
        verified.add(p)
        return true
      }
    }
  }
  // A bare file name (`fonts.ts`, `SKILL.md`) may live anywhere.
  if (!p.includes("/") && tracked.some((f) => f.endsWith("/" + p) || f === p)) {
    verified.add(p)
    return true
  }
  // Gitignored build output (out/, dist/, catalog_builtin/, .playwright-mcp/) may not exist yet.
  // Asked only for missing paths: each check is a git process.
  if (PATH_ROOTS.some((root) => ignored(root + p) || ignored(root + p.replace(/\/?$/, "/")))) return true
  problems.push(`${where}: path \`${raw}\` not found`)
  return true
}

function checkName(span, where) {
  let name = null
  let full = null
  let m
  if ((m = span.match(/^@([A-Za-z_][\w.]*)(\(.*\))?$/))) {
    full = m[1] // decorator: the whole dotted name must appear
  } else if ((m = span.match(/^<\/?([A-Z][A-Za-z0-9]*)[\s/>]/)) || (m = span.match(/^<([A-Z][A-Za-z0-9]*)>?$/))) {
    name = m[1]
  } else if ((m = span.match(/^([A-Za-z_][\w.]*)\(.*\)$/))) {
    // `athena.audit.record(...)`: the code says `audit.record(`, so the last two
    // segments must appear together. A bare call only needs its name.
    full = m[1].includes(".") ? m[1].split(".").slice(-2).join(".") : null
    name = m[1].split(".").pop()
  } else if (/^[a-z_]\w*(\.[A-Za-z_]\w*){2,}$/.test(span)) {
    full = span.split(".").slice(-2).join(".") // `pytest.mark.skipif`, `app.state.package_jobs`
  } else if (/^[a-z][a-z0-9]*(_[a-z0-9]+)+$/.test(span) && span.length >= 5) {
    name = span // snake_case
  } else if (/^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$/.test(span)) {
    name = span // CONSTANT_NAME
  } else if (/^[A-Z][a-z0-9]+([A-Z][a-z0-9]*)+$/.test(span)) {
    name = span // CamelCase
  } else if (/^[a-z][a-z0-9]+([A-Z][a-z0-9]*)+$/.test(span)) {
    name = span // camelCase
  } else {
    return
  }
  const shown = full ?? name
  if (EXTERNAL_PREFIXES.some((x) => span.startsWith(x))) return
  if (EXTERNAL.has(shown) || EXTERNAL.has(name ?? "") || EXTERNAL.has(span)) return
  // `conftest.make_app()`: a module-qualified name is fine when the module is a real
  // file and defines the name.
  const [qualifier, last] = (full ?? "").split(".")
  const definedIn = (q, n) =>
    tracked.some(
      (f) =>
        /\.(py|ts|tsx)$/.test(f) &&
        f.split("/").pop().split(".")[0] === q &&
        new RegExp(`\\b${n}\\b`).test(safeRead(f))
    )
  const ok = full ? corpus.includes(full) || definedIn(qualifier, last) : words.has(name)
  if (ok) verified.add(shown)
  else problems.push(`${where}: name \`${span}\` not found in the code`)
}

function projectSkills() {
  const lock = existsSync("skills-lock.json") ? JSON.parse(readFileSync("skills-lock.json", "utf8")) : {}
  const thirdParty = new Set(Object.keys(lock.skills ?? {}))
  return git(["ls-files", ".agents/skills/*/SKILL.md"]).filter((f) => !thirdParty.has(f.split("/")[2]))
}

function ignored(p) {
  try {
    execFileSync("git", ["check-ignore", "-q", "--no-index", p], { stdio: "ignore" })
    return true
  } catch {
    return false
  }
}

function git(args) {
  return execFileSync("git", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }).split("\n").filter(Boolean)
}

function safeRead(f) {
  try {
    return statSync(f).size < 4 * 1024 * 1024 ? readFileSync(f, "utf8") : ""
  } catch {
    return ""
  }
}
