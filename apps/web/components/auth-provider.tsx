"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import {
  api,
  onUnauthorized,
  setCsrfToken,
  type Schemas,
} from "@workspace/api-client"
import { Spinner } from "@workspace/ui/components/spinner"

export type User = Schemas["UserOut"]

type AuthState = {
  user: User
  logout: () => Promise<void>
}

const AuthContext = React.createContext<AuthState | null>(null)

/**
 * Gate for every signed-in page: sends the browser to /setup on first run and to
 * /login without a session. The data is protected by the API; this is only routing.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [user, setUser] = React.useState<User | null>(null)

  React.useEffect(() => {
    let cancelled = false
    onUnauthorized(() => router.replace("/login/"))
    api.GET("/api/auth/status").then(({ data }) => {
      if (cancelled) return
      if (!data) return router.replace("/login/")
      if (data.setup_required) return router.replace("/setup/")
      if (!data.user) return router.replace("/login/")
      setCsrfToken(data.csrf_token ?? null)
      setUser(data.user)
    })
    return () => {
      cancelled = true
      onUnauthorized(null)
    }
  }, [router])

  const logout = React.useCallback(async () => {
    await api.POST("/api/auth/logout")
    setCsrfToken(null)
    router.replace("/login/")
  }, [router])

  const value = React.useMemo(
    () => (user ? { user, logout } : null),
    [user, logout]
  )

  if (!value) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    )
  }
  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth(): AuthState {
  const ctx = React.useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>")
  return ctx
}
