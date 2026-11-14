"use client"

import * as React from "react"
import { useTheme } from "next-themes"

import { api, errorMessage } from "@workspace/api-client"
import { toast } from "@workspace/ui/components/toast"

import {
  type Appearance,
  applyAppearance,
  normalize,
  storedAppearance,
} from "@/lib/appearance"

type Next = Appearance | ((current: Appearance) => Appearance)

type AppearanceState = {
  appearance: Appearance
  /**
   * Apply right away (the whole UI updates), then save to the server. Pass a function
   * to build on the latest settings, so quick successive changes don't undo each other.
   */
  update: (next: Next) => void
  /** True from the first change until the server has the latest settings. */
  saving: boolean
}

const AppearanceContext = React.createContext<AppearanceState | null>(null)

const SAVE_DELAY_MS = 400

/**
 * The signed-in user's appearance. On load it fetches the saved settings (they follow
 * the account to other browsers) and applies them; the inline script in app/layout.tsx
 * has already painted the copy remembered in this browser.
 */
export function AppearanceProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const { theme, setTheme } = useTheme()
  const [appearance, setAppearance] = React.useState<Appearance>(
    () => storedAppearance() ?? normalize(null)
  )
  const [saving, setSaving] = React.useState(false)
  /** The settings on screen right now, readable from callbacks without re-creating them. */
  const current = React.useRef(appearance)
  const saved = React.useRef<Appearance | null>(null)
  const timer = React.useRef<number | undefined>(undefined)
  /** The mode we last asked next-themes for, to tell our changes from the hotkey's. */
  const requestedMode = React.useRef<string | null>(null)
  // next-themes gives setTheme a new identity when the theme changes; keep the latest
  // in a ref so nothing below re-runs (re-running the load would undo unsaved changes).
  const setThemeRef = React.useRef(setTheme)
  React.useEffect(() => {
    setThemeRef.current = setTheme
  }, [setTheme])

  const show = React.useCallback((next: Appearance) => {
    current.current = next
    setAppearance(next)
    applyAppearance(next)
    requestedMode.current = next.mode
    setThemeRef.current(next.mode)
  }, [])

  // Once per sign-in: the account's settings win over this browser's copy.
  React.useEffect(() => {
    let cancelled = false
    void api.GET("/api/settings/appearance").then(({ data }) => {
      if (cancelled || !data) return
      const next = normalize(data)
      saved.current = next
      // Don't clobber a change made while the request was in flight.
      if (timer.current === undefined) show(next)
    })
    return () => {
      cancelled = true
    }
  }, [show])

  React.useEffect(() => () => window.clearTimeout(timer.current), [])

  const update = React.useCallback(
    (nextOrFn: Next) => {
      const next =
        typeof nextOrFn === "function" ? nextOrFn(current.current) : nextOrFn
      show(next)
      setSaving(true)
      window.clearTimeout(timer.current)
      // Clicking through swatches shouldn't send a request per click.
      timer.current = window.setTimeout(async () => {
        const { data, error } = await api.PUT("/api/settings/appearance", {
          body: next,
        })
        if (current.current !== next) return // a newer change has its own save
        timer.current = undefined
        setSaving(false)
        if (data) {
          saved.current = normalize(data)
          return
        }
        toast.add({
          type: "error",
          title: "Couldn't save your appearance settings",
          description: errorMessage(error),
        })
        if (saved.current) show(saved.current)
      }, SAVE_DELAY_MS)
    },
    [show]
  )

  // Dark mode can also change outside Settings (the "d" hotkey): keep the saved mode in step.
  React.useEffect(() => {
    const isMode = theme === "light" || theme === "dark" || theme === "system"
    if (saved.current && isMode && theme !== requestedMode.current) {
      update((a) => ({ ...a, mode: theme }))
    }
  }, [theme, update])

  const value = React.useMemo(
    () => ({ appearance, update, saving }),
    [appearance, update, saving]
  )
  return (
    <AppearanceContext.Provider value={value}>
      {children}
    </AppearanceContext.Provider>
  )
}

export function useAppearance(): AppearanceState {
  const value = React.useContext(AppearanceContext)
  if (!value) {
    throw new Error("useAppearance must be used inside <AppearanceProvider>")
  }
  return value
}
