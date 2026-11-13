"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { api, errorMessage, setCsrfToken } from "@workspace/api-client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"

import { CredentialsForm } from "@/components/credentials-form"

export default function LoginPage() {
  const router = useRouter()

  React.useEffect(() => {
    api.GET("/api/auth/status").then(({ data }) => {
      if (data?.setup_required) router.replace("/setup/")
      else if (data?.user) router.replace("/")
    })
  }, [router])

  return (
    <>
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Sign in</CardTitle>
          <CardDescription>Sign in to manage this server.</CardDescription>
        </CardHeader>
        <CardContent>
          <CredentialsForm
            mode="login"
            submitLabel="Sign in"
            onSubmit={async (credentials) => {
              const { data, error } = await api.POST("/api/auth/login", {
                body: credentials,
              })
              if (!data) return errorMessage(error, "Couldn't sign in")
              setCsrfToken(data.csrf_token ?? null)
              router.replace("/")
              return null
            }}
          />
        </CardContent>
      </Card>
      <p className="px-6 text-center text-sm text-balance text-muted-foreground">
        Forgot your password? On the server, run{" "}
        <code className="font-mono text-foreground">
          athena admin reset-password
        </code>{" "}
        (with <code className="font-mono text-foreground">sudo</code> on Linux).
      </p>
    </>
  )
}
