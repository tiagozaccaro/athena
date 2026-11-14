#!/usr/bin/env node
// Generates the runtime appearance CSS (docs/mvp-design.md §5.4) from the shadcn registry.
//
//   node scripts/gen-theme-css.mjs        (or: pnpm gen:theme)
//
// shadcn applies presets at init time. Athena switches them at runtime instead, so this
// script asks the registry (the same /init endpoint the shadcn CLI uses) for every base
// color, theme, chart color and radius, works out which CSS variables each setting owns,
// and writes attribute-scoped blocks:
//
//   :root[data-base="stone"]      background, foreground, muted, border, sidebar, …
//   :root[data-theme="blue"]      primary, secondary, sidebar-primary, charts (default)
//   :root[data-chart="emerald"]   chart-1…5 (overrides the theme's charts)
//   :root[data-radius="large"]    radius
//
// …each with a `.dark` twin. It fails instead of guessing if the registry's variables
// stop splitting cleanly between settings. The output is committed, so builds don't need
// the network. Run it after upgrading shadcn.

import { writeFileSync } from "node:fs"
import { createRequire } from "node:module"
import { dirname, join } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const OUT_CSS = join(ROOT, "packages/ui/src/styles/themes.css")
const OUT_JSON = join(ROOT, "packages/ui/src/styles/themes.json")
const REGISTRY = "https://ui.shadcn.com/init"

const require = createRequire(join(ROOT, "packages/ui/package.json"))
const preset = await import(pathToFileURL(require.resolve("shadcn/preset")).href)
const {
  DEFAULT_PRESET_CONFIG: DEF,
  PRESET_BASE_COLORS,
  PRESET_THEMES,
  PRESET_CHART_COLORS,
  PRESET_RADII,
  PRESET_FONTS,
} = preset

// Everything that isn't a color stays at the preset Athena is built with (b0).
const FIXED = {
  base: "base",
  style: DEF.style,
  iconLibrary: DEF.iconLibrary,
  font: DEF.font,
  rtl: "false",
  menuAccent: DEF.menuAccent,
  menuColor: DEF.menuColor,
}

class Unavailable extends Error {}

async function fetchVars({ baseColor, theme, chartColor, radius = "default" }) {
  const params = new URLSearchParams({ ...FIXED, baseColor, theme, radius })
  // Like the CLI: "neutral" charts means "follow the theme", sent as no chartColor at all.
  if (chartColor && chartColor !== "neutral") params.set("chartColor", chartColor)
  for (let attempt = 1; ; attempt++) {
    const res = await fetch(`${REGISTRY}?${params}`, {
      headers: { "user-agent": "athena-theme-gen" },
    })
    if (res.status === 400) throw new Unavailable((await res.json()).error ?? "unavailable")
    if (res.ok) {
      const body = await res.json()
      if (!body.cssVars?.light || !body.cssVars?.dark) throw new Error(`no cssVars for ${params}`)
      return body.cssVars
    }
    if (attempt >= 3) throw new Error(`${res.status} from ${REGISTRY}?${params}`)
    await new Promise((r) => setTimeout(r, 1000 * attempt))
  }
}

async function tryFetch(args, skipped, label) {
  try {
    return await fetchVars(args)
  } catch (err) {
    if (!(err instanceof Unavailable)) throw err
    skipped.push(`${label}: ${err.message}`)
    return null
  }
}

/** Keys whose light or dark value differs between two variable sets. */
function changed(a, b) {
  const keys = new Set()
  for (const mode of ["light", "dark"]) {
    for (const k of new Set([...Object.keys(a[mode]), ...Object.keys(b[mode])])) {
      if (a[mode][k] !== b[mode][k]) keys.add(k)
    }
  }
  return keys
}

/** Per-mode keys whose value differs: { light: Set, dark: Set }. */
function changedByMode(a, b) {
  const out = { light: new Set(), dark: new Set() }
  for (const mode of ["light", "dark"]) {
    for (const k of new Set([...Object.keys(a[mode]), ...Object.keys(b[mode])])) {
      if (k !== "radius" && a[mode][k] !== b[mode][k]) out[mode].add(k)
    }
  }
  return out
}

/** The given keys of a variable set: an iterable for both modes, or { light, dark }. */
function pick(vars, keys) {
  const out = { light: {}, dark: {} }
  for (const mode of ["light", "dark"]) {
    const modeKeys = keys[mode] ?? keys
    for (const k of modeKeys) if (vars[mode][k] !== undefined) out[mode][k] = vars[mode][k]
  }
  return out
}

const skipped = []
const isChart = (k) => /^chart-\d$/.test(k)

// 1. Base colors, each with its matching theme ("stone" + "stone").
const bases = {}
for (const b of PRESET_BASE_COLORS) {
  const vars = await tryFetch({ baseColor: b, theme: b }, skipped, `base ${b}`)
  if (vars) bases[b] = vars
}
if (!bases.neutral) throw new Error("the registry has no neutral base color")
const baseNames = Object.keys(bases)

// 2. Colored themes. A theme owns whatever it changes compared with the base's own look.
//    Most set primary/secondary/sidebar-primary and the charts, but some set more (rose
//    also sets the dark sidebar), so each theme gets its own key set. Comparing on two
//    bases catches keys that happen to equal one base's value.
const [baseA, baseB] = [
  "neutral",
  baseNames.find((b) => b !== "neutral") ?? "neutral",
]
const coloredThemes = {}
const themeKeysOf = {}
for (const t of PRESET_THEMES.filter((t) => !PRESET_BASE_COLORS.includes(t))) {
  const onA = await tryFetch({ baseColor: baseA, theme: t }, skipped, `theme ${t}`)
  if (!onA) continue
  const onB = await fetchVars({ baseColor: baseB, theme: t })
  // Per mode: rose sets the sidebar in dark mode only.
  const a = changedByMode(bases[baseA], onA)
  const b = changedByMode(bases[baseB], onB)
  const keys = { light: new Set([...a.light, ...b.light]), dark: new Set([...a.dark, ...b.dark]) }
  for (const mode of ["light", "dark"]) {
    for (const k of keys[mode]) {
      if (onA[mode][k] !== onB[mode][k]) {
        throw new Error(`theme ${t} sets ${mode} ${k} differently on ${baseA} and ${baseB}`)
      }
    }
  }
  coloredThemes[t] = onA
  themeKeysOf[t] = keys
}
if (Object.keys(coloredThemes).length === 0) throw new Error("the registry served no themes")
// A base-named theme ("stone" on "stone") sets the usual theme keys from its base.
const commonThemeKeys = { light: new Set(), dark: new Set() }
for (const keys of Object.values(themeKeysOf)) {
  for (const mode of ["light", "dark"]) for (const k of keys[mode]) commonThemeKeys[mode].add(k)
}
// Base blocks carry every variable; theme and chart blocks come later and override.
const allKeys = (vars) =>
  [...new Set([...Object.keys(vars.light), ...Object.keys(vars.dark)])].filter((k) => k !== "radius")

/** base ⊕ theme ⊕ chart, the way the generated CSS composes them. */
function compose(base, theme, chart) {
  const layers = [pick(bases[base], allKeys(bases[base])), themes[theme], chart ? charts[chart] : null]
  const out = { light: {}, dark: {} }
  for (const layer of layers.filter(Boolean)) {
    Object.assign(out.light, layer.light)
    Object.assign(out.dark, layer.dark)
  }
  return out
}

// 4. Explicit chart colors: colored ones on neutral/neutral, base-named ones on their base.
const charts = {}
for (const c of PRESET_CHART_COLORS.filter((c) => c !== "neutral")) {
  const onBase = PRESET_BASE_COLORS.includes(c)
  if (onBase && !bases[c]) continue
  const vars = await tryFetch(
    onBase ? { baseColor: c, theme: c, chartColor: c } : { baseColor: "neutral", theme: "neutral", chartColor: c },
    skipped,
    `chart ${c}`
  )
  if (vars) charts[c] = pick(vars, Object.keys(vars.light).filter(isChart))
}

const themes = {
  ...Object.fromEntries(baseNames.map((b) => [b, pick(bases[b], commonThemeKeys)])),
  ...Object.fromEntries(
    Object.entries(coloredThemes).map(([t, v]) => [t, pick(v, themeKeysOf[t])])
  ),
}

// 5. Verify the composition against the registry on a third base, for every colored
//    theme, plus one explicit chart color. Fails instead of shipping wrong colors.
const baseC = baseNames.find((b) => b !== baseA && b !== baseB) ?? baseB
const checks = Object.keys(coloredThemes).map((t) => [baseC, t, undefined])
const someChart = Object.keys(charts).find((c) => !PRESET_BASE_COLORS.includes(c))
if (someChart) checks.push([baseB, Object.keys(coloredThemes)[0], someChart])
for (const [b, t, c] of checks) {
  const real = await fetchVars({ baseColor: b, theme: t, chartColor: c })
  const ours = compose(b, t, c)
  const diff = [...changed(pick(real, allKeys(real)), ours)]
  if (diff.length) {
    throw new Error(
      `${b} + ${t}${c ? ` + chart ${c}` : ""} doesn't compose (differs in ${diff.join(", ")}); ` +
        "the registry's model changed, update this script"
    )
  }
}

// 6. Radii (one value, light only).
const radii = {}
for (const r of PRESET_RADII) {
  const vars = await tryFetch({ baseColor: "neutral", theme: "neutral", radius: r }, skipped, `radius ${r}`)
  if (vars?.light.radius !== undefined) radii[r] = vars.light.radius
}

// ------------------------------------------------------------------ output

function block(selector, vars) {
  const lines = Object.entries(vars).map(([k, v]) => `  --${k}: ${v};`)
  return lines.length ? `${selector} {\n${lines.join("\n")}\n}\n` : ""
}

function pair(attr, name, vars) {
  return (
    block(`:root[data-${attr}="${name}"]`, vars.light) +
    block(`:root.dark[data-${attr}="${name}"]`, vars.dark)
  )
}


let css = `/*
 * GENERATED by scripts/gen-theme-css.mjs from the shadcn registry. Don't edit by hand;
 * run \`pnpm gen:theme\` after upgrading shadcn.
 *
 * Runtime appearance (docs/mvp-design.md §5.4): <html> carries data-base, data-theme,
 * data-chart, data-radius, data-font and data-font-heading, set before first paint by the inline script in
 * apps/web/app/layout.tsx. Order matters: chart blocks come after theme blocks so an
 * explicit chart color beats the theme's default charts.
 */

/* Base colors */
`
for (const b of baseNames) css += pair("base", b, pick(bases[b], allKeys(bases[b])))
css += "\n/* Themes (a base-named theme is that base's own accent) */\n"
for (const [t, vars] of Object.entries(themes)) css += pair("theme", t, vars)
css += "\n/* Explicit chart colors (\"neutral\" means follow the theme: no block) */\n"
for (const [c, vars] of Object.entries(charts)) css += pair("chart", c, vars)
css += "\n/* Radius */\n"
for (const [r, value] of Object.entries(radii)) css += block(`:root[data-radius="${r}"]`, { radius: value })

// Fonts: apps/web/lib/fonts.ts loads every preset font with next/font as --font-<id>.
// Headings use --app-font-heading (globals.css maps Tailwind's font-heading to it).
css += "\n/* Fonts (loaded by apps/web/lib/fonts.ts) */\n"
for (const f of PRESET_FONTS) css += block(`:root[data-font="${f}"]`, { "font-sans": `var(--font-${f})` })
css += block(`:root[data-font-heading="inherit"]`, { "app-font-heading": "var(--font-sans)" })
for (const f of PRESET_FONTS) {
  css += block(`:root[data-font-heading="${f}"]`, { "app-font-heading": `var(--font-${f})` })
}

writeFileSync(OUT_CSS, css)

// Options and swatches for the Settings page (only what the registry actually serves).
const manifest = {
  bases: baseNames.map((b) => ({
    id: b,
    swatch: bases[b].light["muted-foreground"] ?? bases[b].light.foreground,
  })),
  themes: Object.entries(themes).map(([id, v]) => ({
    id,
    matchesBase: baseNames.includes(id),
    swatch: v.light.primary,
  })),
  charts: Object.entries(charts).map(([id, v]) => ({
    id,
    matchesBase: baseNames.includes(id),
    swatch: v.light["chart-3"] ?? v.light["chart-1"],
  })),
  radii: Object.entries(radii).map(([id, value]) => ({ id, value })),
  fonts: [...PRESET_FONTS],
  skipped,
}
writeFileSync(OUT_JSON, `${JSON.stringify(manifest, null, 2)}\n`)

console.log(
  `wrote ${OUT_CSS.replace(ROOT + "/", "")}: ${baseNames.length} bases, ` +
    `${Object.keys(themes).length} themes, ${Object.keys(charts).length} charts, ` +
    `${Object.keys(radii).length} radii`
)
console.log(`theme keys (light): ${[...commonThemeKeys.light].join(" ")}`)
console.log(`theme keys (dark): ${[...commonThemeKeys.dark].join(" ")}`)
console.log(`verified ${checks.length} combinations against the registry`)
if (skipped.length) console.log(`skipped (not served by the registry):\n  ${skipped.join("\n  ")}`)
