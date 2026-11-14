"use client"

import * as React from "react"

import { api, errorMessage } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import { useAuth } from "@/components/auth-provider"

const MIN_LENGTH = 8

/** Settings → Account: who you are, and changing your password. */
export function AccountForm() {
  const { user } = useAuth()
  const formRef = React.useRef<HTMLFormElement>(null)
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [mismatch, setMismatch] = React.useState(false)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const current = String(form.get("current") ?? "")
    const next = String(form.get("new") ?? "")
    if (next !== String(form.get("confirm") ?? "")) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    setError(null)
    setPending(true)
    const { error: err, response } = await api.POST("/api/auth/password", {
      body: { current_password: current, new_password: next },
    })
    setPending(false)
    if (response.ok) {
      formRef.current?.reset()
      toast.add({
        type: "success",
        title: "Password changed",
        description:
          "Other browsers signed in to this account were signed out.",
      })
      return
    }
    setError(errorMessage(err, "Couldn't change the password"))
  }

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>
            Signed in as{" "}
            <span className="font-medium text-foreground">{user.username}</span>
            {user.is_admin ? " · administrator" : ""}
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>
            Your other sessions are signed out; this one stays signed in.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form ref={formRef} onSubmit={submit} className="max-w-sm">
            {/* Lets password managers attach the new password to the right account. */}
            <input
              type="text"
              name="username"
              autoComplete="username"
              value={user.username}
              readOnly
              hidden
            />
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="current">Current password</FieldLabel>
                <Input
                  id="current"
                  name="current"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="new">New password</FieldLabel>
                <Input
                  id="new"
                  name="new"
                  type="password"
                  autoComplete="new-password"
                  minLength={MIN_LENGTH}
                  required
                />
                <FieldDescription>
                  At least {MIN_LENGTH} characters.
                </FieldDescription>
              </Field>
              <Field data-invalid={mismatch || undefined}>
                <FieldLabel htmlFor="confirm">Confirm new password</FieldLabel>
                <Input
                  id="confirm"
                  name="confirm"
                  type="password"
                  autoComplete="new-password"
                  aria-invalid={mismatch || undefined}
                  required
                />
                {mismatch ? (
                  <FieldError>Passwords don&apos;t match.</FieldError>
                ) : null}
              </Field>
              {error ? (
                <Field data-invalid>
                  <FieldError>{error}</FieldError>
                </Field>
              ) : null}
              <Field orientation="horizontal">
                <Button type="submit" disabled={pending}>
                  {pending ? <Spinner data-icon="inline-start" /> : null}
                  Change password
                </Button>
              </Field>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
