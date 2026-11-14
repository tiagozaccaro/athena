import {
  DEFAULT_PRESET_CONFIG,
  decodePreset,
  encodePreset,
  type PresetConfig,
} from "shadcn/preset"

import type { Schemas } from "@workspace/api-client"
import manifest from "@workspace/ui/themes.json"

/**
 * Runtime appearance (docs/mvp-design.md §5.4). The options come from
 * packages/ui/src/styles/themes.json, which `pnpm gen:theme` writes from the shadcn
 * registry next to the CSS it generates, so the UI only offers what the CSS defines.
 */
export type Appearance = Schemas["Appearance"]
export type Mode = Appearance["mode"]

export const STORAGE_KEY = "athena-appearance"

export const DEFAULT_APPEARANCE: Appearance = {
  mode: "system",
  base_color: "neutral",
  theme: "neutral",
  chart_color: "neutral",
  font: "inter",
  font_heading: "inherit",
  radius: "default",
}

export const BASES = manifest.bases
export const THEMES = manifest.themes
export const CHARTS = manifest.charts
export const RADII = manifest.radii
export const FONTS = manifest.fonts

const baseIds = new Set(BASES.map((b) => b.id))
const coloredThemes = new Set(
  THEMES.filter((t) => !t.matchesBase).map((t) => t.id)
)
const coloredCharts = new Set(
  CHARTS.filter((c) => !c.matchesBase).map((c) => c.id)
)
const chartIds = new Set(CHARTS.map((c) => c.id))
const radiusIds = new Set(RADII.map((r) => r.id))
const fontIds = new Set(FONTS)

/** "playfair-display" → "Playfair Display", "dm-sans" → "DM Sans". */
export function label(id: string): string {
  const special: Record<string, string> = {
    dm: "DM",
    ibm: "IBM",
    eb: "EB",
  }
  return id
    .split("-")
    .map((w) => special[w] ?? w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

/**
 * Valid settings only. Unknown ids (from an older or newer Athena, or a hand-edited
 * value) fall back to the default; a base-named theme or chart only counts when it is
 * the current base's own.
 */
export function normalize(
  input: Partial<Appearance> | null | undefined
): Appearance {
  const a = { ...DEFAULT_APPEARANCE, ...(input ?? {}) }
  const mode: Mode = ["light", "dark", "system"].includes(a.mode)
    ? a.mode
    : "system"
  const base = baseIds.has(a.base_color)
    ? a.base_color
    : DEFAULT_APPEARANCE.base_color
  const theme = coloredThemes.has(a.theme) || a.theme === base ? a.theme : base
  const chart =
    a.chart_color === "neutral" ||
    coloredCharts.has(a.chart_color) ||
    (a.chart_color === base && chartIds.has(base))
      ? a.chart_color
      : "neutral"
  return {
    mode,
    base_color: base,
    theme,
    chart_color: chart,
    font: fontIds.has(a.font) ? a.font : DEFAULT_APPEARANCE.font,
    font_heading:
      a.font_heading === "inherit" || fontIds.has(a.font_heading)
        ? a.font_heading
        : "inherit",
    radius: radiusIds.has(a.radius) ? a.radius : DEFAULT_APPEARANCE.radius,
  }
}

/** Changing the base keeps a "match the base" theme and chart matching the new base. */
export function withBase(a: Appearance, base: string): Appearance {
  return normalize({
    ...a,
    base_color: base,
    theme: a.theme === a.base_color ? base : a.theme,
    chart_color: a.chart_color === a.base_color ? base : a.chart_color,
  })
}

/** The data-* attributes for <html>. Charts that follow the theme get no attribute. */
export function attributes(a: Appearance): Record<string, string | null> {
  return {
    "data-base": a.base_color,
    "data-theme": a.theme,
    "data-chart": a.chart_color === "neutral" ? null : a.chart_color,
    "data-radius": a.radius,
    "data-font": a.font,
    "data-font-heading": a.font_heading,
  }
}

/** The server-rendered defaults; the inline script replaces them before first paint. */
export const DEFAULT_ATTRIBUTES = Object.fromEntries(
  Object.entries(attributes(DEFAULT_APPEARANCE)).filter(([, v]) => v !== null)
) as Record<string, string>

/** Set the attributes on <html> and remember them for the next page load. */
export function applyAppearance(a: Appearance): void {
  const root = document.documentElement
  for (const [name, value] of Object.entries(attributes(a))) {
    if (value === null) root.removeAttribute(name)
    else root.setAttribute(name, value)
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(a))
  } catch {
    // Private mode or storage disabled: the settings still apply to this page.
  }
}

export function storedAppearance(): Appearance | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalize(JSON.parse(raw) as Partial<Appearance>) : null
  } catch {
    return null
  }
}

/**
 * Runs in <head> before the first paint: copies the stored settings onto <html>.
 * Values are checked against the same id pattern the server enforces, so a tampered
 * localStorage can't inject anything; unknown-but-valid ids just match no CSS.
 */
export const APPEARANCE_SCRIPT = `(function(){try{var a=JSON.parse(localStorage.getItem(${JSON.stringify(
  STORAGE_KEY
)})||"null");if(!a)return;var r=document.documentElement,ok=/^[a-z0-9-]{1,32}$/,m={"data-base":a.base_color,"data-theme":a.theme,"data-chart":a.chart_color,"data-radius":a.radius,"data-font":a.font,"data-font-heading":a.font_heading};for(var k in m){var v=m[k];if(k==="data-chart"&&v==="neutral"){r.removeAttribute(k);continue}if(typeof v==="string"&&ok.test(v))r.setAttribute(k,v)}}catch(e){}})()`

// ------------------------------------------------------------------ preset codes

// Athena is built with preset b0: only its colors, fonts and radius switch at runtime.
const BUILT_WITH = DEFAULT_PRESET_CONFIG

/** The shadcn preset code for these settings (style, icons and menus stay b0's). */
export function toPresetCode(a: Appearance): string {
  return encodePreset({
    ...BUILT_WITH,
    baseColor: a.base_color as PresetConfig["baseColor"],
    theme: a.theme as PresetConfig["theme"],
    chartColor: a.chart_color as PresetConfig["chartColor"],
    font: a.font as PresetConfig["font"],
    fontHeading: a.font_heading as PresetConfig["fontHeading"],
    radius: a.radius as PresetConfig["radius"],
  })
}

export type PresetImport = {
  appearance: Appearance
  /** Human-readable parts of the code Athena can't apply (yet). */
  ignored: string[]
}

/** Settings from a preset code (keeping the current mode), or null if it isn't one. */
export function fromPresetCode(
  code: string,
  current: Appearance
): PresetImport | null {
  const config = decodePreset(code.trim())
  if (!config) return null
  const ignored: string[] = []
  if (config.style !== BUILT_WITH.style)
    ignored.push(`the ${label(config.style)} style`)
  if (config.iconLibrary !== BUILT_WITH.iconLibrary) {
    ignored.push(`${label(config.iconLibrary)} icons`)
  }
  if (
    config.menuColor !== BUILT_WITH.menuColor ||
    config.menuAccent !== BUILT_WITH.menuAccent
  ) {
    ignored.push("menu colors")
  }
  const appearance = normalize({
    mode: current.mode,
    base_color: config.baseColor,
    theme: config.theme,
    chart_color: config.chartColor ?? "neutral",
    font: config.font,
    font_heading: config.fontHeading,
    radius: config.radius,
  })
  if (appearance.base_color !== config.baseColor) {
    ignored.push(`the ${label(config.baseColor)} base color`)
  }
  if (appearance.theme !== config.theme && config.theme !== config.baseColor) {
    ignored.push(`the ${label(config.theme)} theme`)
  }
  return { appearance, ignored }
}
