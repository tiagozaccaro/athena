const UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]

/** 1536 → "1.5 KB", 999 → "999 B", 1023.6 → "1.0 KB" (never "1024 B"). */
export function formatBytes(bytes: number, digits = 1): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B"
  let i = 0
  let value = bytes
  // Move up a unit once the rounded number would reach four digits.
  while (value >= 999.5 && i < UNITS.length - 1) {
    value /= 1024
    i++
  }
  return `${value.toFixed(i === 0 || value >= 100 ? 0 : digits)} ${UNITS[i]}`
}

export function formatRate(bytesPerSecond: number): string {
  return `${formatBytes(bytesPerSecond)}/s`
}

export function formatPercent(value: number): string {
  return `${Math.round(value)}%`
}

/** Seconds → "3d 4h", "5h 12m", "8m". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

/** Unix seconds → local "14:05:32". */
export function formatClock(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}
