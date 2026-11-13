"use client"

import * as React from "react"

import { Button } from "@workspace/ui/components/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Spinner } from "@workspace/ui/components/spinner"

export type Credentials = { username: string; password: string }

/** Username + password form shared by /setup (with confirmation) and /login. */
export function CredentialsForm({
  mode,
  submitLabel,
  onSubmit,
}: {
  mode: "setup" | "login"
  submitLabel: string
  /** Resolves to an error message, or null on success. */
  onSubmit: (credentials: Credentials) => Promise<string | null>
}) {
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [mismatch, setMismatch] = React.useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const username = String(form.get("username") ?? "").trim()
    const password = String(form.get("password") ?? "")
    if (mode === "setup" && password !== String(form.get("confirm") ?? "")) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    setPending(true)
    setError(await onSubmit({ username, password }))
    setPending(false)
  }

  return (
    <form onSubmit={handleSubmit}>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="username">Username</FieldLabel>
          <Input
            id="username"
            name="username"
            autoComplete="username"
            defaultValue={mode === "setup" ? "admin" : undefined}
            required
            autoFocus
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="password">Password</FieldLabel>
          <Input
            id="password"
            name="password"
            type="password"
            autoComplete={
              mode === "setup" ? "new-password" : "current-password"
            }
            minLength={mode === "setup" ? 8 : undefined}
            required
          />
          {mode === "setup" ? (
            <FieldDescription>At least 8 characters.</FieldDescription>
          ) : null}
        </Field>
        {mode === "setup" ? (
          <Field data-invalid={mismatch || undefined}>
            <FieldLabel htmlFor="confirm">Confirm password</FieldLabel>
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
        ) : null}
        {error ? (
          <Field data-invalid>
            <FieldError>{error}</FieldError>
          </Field>
        ) : null}
        <Field>
          <Button type="submit" disabled={pending}>
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {submitLabel}
          </Button>
        </Field>
      </FieldGroup>
    </form>
  )
}
