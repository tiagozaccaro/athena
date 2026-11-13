#!/usr/bin/env node
// Syncs MCP servers from .mcp.json (the single source of truth) to other agents.
//
//   node scripts/agents-sync.mjs           write the "mcp" block of opencode.json
//   node scripts/agents-sync.mjs --check   exit 1 if opencode.json is out of date (for CI)
//   node scripts/agents-sync.mjs --hermes  trust this repo's skills in Hermes and register
//                                          any missing MCP servers (via the hermes CLI)
//   node scripts/agents-sync.mjs --hermes-print
//                                          only print the mcp_servers block for ~/.hermes/config.yaml
//
// Hermes Agent only reads MCP servers from its user-level config (~/.hermes/config.yaml),
// so --hermes changes that file through the official CLI. Existing servers are left alone.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const args = new Set(process.argv.slice(2));

const servers = JSON.parse(readFileSync(join(root, ".mcp.json"), "utf8")).mcpServers ?? {};

// OpenCode 2.x config shape: { mcp: { servers: { <name>: {...} } } }
function toOpenCode(s) {
  if (s.url) {
    return { type: "remote", url: s.url, ...(s.headers && { headers: s.headers }) };
  }
  return {
    type: "local",
    command: [s.command, ...(s.args ?? [])],
    ...(s.env && { environment: s.env }),
  };
}

function yamlValue(v) {
  return JSON.stringify(v); // JSON scalars, arrays and objects are valid YAML flow syntax
}

function toHermesYaml() {
  const lines = ["mcp_servers:"];
  for (const [name, s] of Object.entries(servers)) {
    lines.push(`  ${name}:`);
    if (s.url) {
      lines.push(`    url: ${yamlValue(s.url)}`);
      if (s.headers) lines.push(`    headers: ${yamlValue(s.headers)}`);
    } else {
      lines.push(`    command: ${yamlValue(s.command)}`);
      lines.push(`    args: ${yamlValue(s.args ?? [])}`);
      if (s.env) lines.push(`    env: ${yamlValue(s.env)}`);
    }
  }
  return lines.join("\n");
}

if (args.has("--hermes-print")) {
  console.log("# Merge into ~/.hermes/config.yaml, then run /reload-mcp in Hermes.");
  console.log("# Also run `hermes skills trust` in this repo so .agents/skills loads.");
  console.log(toHermesYaml());
  process.exit(0);
}

if (args.has("--hermes")) {
  const shell = process.platform === "win32"; // hermes is a .cmd/.exe shim on Windows
  // `hermes mcp add` asks "Enable all N tools? [Y/n/select]" and cancels (exit 0) on EOF,
  // so answer "Y" on stdin and verify with `hermes mcp list` afterwards.
  const hermes = (...a) => spawnSync("hermes", a, { cwd: root, encoding: "utf8", shell, input: "Y\n" });
  const isListed = (name) =>
    new RegExp(`^\\s*${name.replace(/[-]/g, "\\-")}\\s`, "m").test(hermes("mcp", "list").stdout ?? "");

  if (hermes("--version").status !== 0) {
    console.error("hermes CLI not found on PATH. Install Hermes Agent, or use --hermes-print.");
    process.exit(1);
  }

  const trust = hermes("skills", "trust", root);
  console.log(trust.status === 0 ? "hermes: trusted project skills (.agents/skills)" : trust.stderr);

  let failed = false;
  for (const [name, s] of Object.entries(servers)) {
    if (isListed(name)) {
      console.log(`hermes: MCP server "${name}" already configured, skipped`);
      continue;
    }
    const cmd = s.url
      ? ["mcp", "add", name, "--url", s.url]
      : [
          "mcp", "add", name, "--command", s.command,
          ...(s.env ? ["--env", ...Object.entries(s.env).map(([k, v]) => `${k}=${v}`)] : []),
          "--args", ...(s.args ?? []),
        ];
    const r = hermes(...cmd);
    if (r.status === 0 && isListed(name)) console.log(`hermes: added MCP server "${name}"`);
    else {
      failed = true;
      console.error(`hermes: failed to add "${name}":\n${r.stdout}${r.stderr}`);
    }
  }
  console.log("Restart Hermes or run /reload-mcp in a running session.");
  process.exit(failed ? 1 : 0);
}

const opencodePath = join(root, "opencode.json");
const existing = existsSync(opencodePath)
  ? JSON.parse(readFileSync(opencodePath, "utf8"))
  : { $schema: "https://opencode.ai/config.json" };

const next = {
  ...existing,
  mcp: {
    ...existing.mcp,
    servers: Object.fromEntries(Object.entries(servers).map(([n, s]) => [n, toOpenCode(s)])),
  },
};
const out = JSON.stringify(next, null, 2) + "\n";

if (args.has("--check")) {
  const current = existsSync(opencodePath) ? readFileSync(opencodePath, "utf8") : "";
  if (current !== out) {
    console.error("opencode.json is out of date. Run: node scripts/agents-sync.mjs");
    process.exit(1);
  }
  console.log("opencode.json is in sync with .mcp.json");
} else {
  writeFileSync(opencodePath, out);
  console.log(`opencode.json: synced ${Object.keys(servers).length} MCP server(s) from .mcp.json`);
}
