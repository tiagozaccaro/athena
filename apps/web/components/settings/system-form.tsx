"use client"

import * as React from "react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Switch } from "@workspace/ui/components/switch"
import { toast } from "@workspace/ui/components/toast"

import { useAuth } from "@/components/auth-provider"

type SystemSettings = Schemas["SystemSettings"]

/** Settings → System: host-wide switches that only admins change. */
export function SystemForm() {
  const { user } = useAuth()
  const [settings, setSettings] = React.useState<SystemSettings | null>(null)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    api
      .GET("/api/settings/system")
      .then(({ data }) => data && setSettings(data))
  }, [])

  async function update(next: SystemSettings) {
    const previous = settings
    setSettings(next)
    setSaving(true)
    const { data, error } = await api.PUT("/api/settings/system", {
      body: next,
    })
    setSaving(false)
    if (data) {
      setSettings(data)
      toast.add({
        type: "success",
        title: data.terminal_enabled
          ? "Terminal turned on"
          : "Terminal turned off",
      })
    } else {
      setSettings(previous)
      toast.add({
        type: "error",
        title: "Couldn't save",
        description: errorMessage(error),
      })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Security</CardTitle>
        <CardDescription>
          Powerful features you can switch off for everyone. Every use is
          written to the audit log.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <Field orientation="horizontal">
            <FieldContent>
              <FieldLabel htmlFor="terminal-enabled">Web terminal</FieldLabel>
              <FieldDescription>
                A shell on this server and in containers, from the browser.
                Turning it off also closes open sessions.
                {!user.is_admin && " Only admins can change this."}
              </FieldDescription>
            </FieldContent>
            <Switch
              id="terminal-enabled"
              checked={settings.terminal_enabled}
              disabled={saving || !user.is_admin}
              onCheckedChange={(checked) =>
                update({ ...settings, terminal_enabled: checked })
              }
            />
          </Field>
        )}
      </CardContent>
    </Card>
  )
}
