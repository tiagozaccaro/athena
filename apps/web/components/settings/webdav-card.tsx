"use client"

import * as React from "react"
import { CopyIcon, KeyRoundIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
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
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@workspace/ui/components/input-group"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Switch } from "@workspace/ui/components/switch"
import { toast } from "@workspace/ui/components/toast"

import { useAuth } from "@/components/auth-provider"
import { useCapability } from "@/components/capabilities-provider"
import { copyText } from "@/lib/clipboard"

type WebDav = Schemas["WebDavOut"]

function CopyField({
  id,
  label,
  value,
}: {
  id: string
  label: string
  value: string
}) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <InputGroup>
        <InputGroupInput id={id} readOnly value={value} className="font-mono" />
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            size="icon-xs"
            aria-label={`Copy ${label.toLowerCase()}`}
            onClick={async () => {
              const ok = await copyText(value)
              toast.add(
                ok
                  ? { type: "success", title: `${label} copied` }
                  : { type: "error", title: "Couldn't copy" }
              )
            }}
          >
            <CopyIcon />
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </Field>
  )
}

/** Settings → System: the WebDAV network share at /dav/. */
export function WebDavCard() {
  const { user } = useAuth()
  const capability = useCapability("shares.webdav")
  const [config, setConfig] = React.useState<WebDav | null>(null)
  const [saving, setSaving] = React.useState(false)
  const [password, setPassword] = React.useState<string | null>(null)

  React.useEffect(() => {
    api.GET("/api/webdav").then(({ data }) => data && setConfig(data))
  }, [])

  if (!capability) return null

  async function toggle(enabled: boolean) {
    setSaving(true)
    const { data, error } = await api.PUT("/api/webdav", { body: { enabled } })
    setSaving(false)
    if (data) {
      setConfig(data)
      toast.add({
        type: "success",
        title: enabled ? "WebDAV turned on" : "WebDAV turned off",
      })
    } else {
      toast.add({
        type: "error",
        title: "Couldn't save",
        description: errorMessage(error),
      })
    }
  }

  async function generate() {
    setSaving(true)
    const { data, error } = await api.POST("/api/webdav/password")
    setSaving(false)
    if (data) {
      setPassword(data.password)
      setConfig((c) =>
        c ? { ...c, username: data.username, has_password: true } : c
      )
    } else {
      toast.add({
        type: "error",
        title: "Couldn't make a password",
        description: errorMessage(error),
      })
    }
  }

  const address =
    typeof window === "undefined"
      ? (config?.path ?? "/dav/")
      : `${window.location.origin}${config?.path ?? "/dav/"}`
  const plainHttp =
    typeof window !== "undefined" && window.location.protocol === "http:"

  return (
    <Card>
      <CardHeader>
        <CardTitle>Network share (WebDAV)</CardTitle>
        <CardDescription>
          Open the file manager&apos;s locations as a drive in Finder, Windows
          Explorer or a Linux file manager.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {config === null ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <FieldGroup>
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor="webdav-enabled">WebDAV</FieldLabel>
                <FieldDescription>
                  Off by default. Anyone with the WebDAV password can read and
                  change every location.
                  {!user.is_admin && " Only admins can change this."}
                </FieldDescription>
              </FieldContent>
              <Switch
                id="webdav-enabled"
                checked={config.enabled}
                disabled={saving || !user.is_admin}
                onCheckedChange={(checked) => void toggle(checked)}
              />
            </Field>
            {config.enabled ? (
              <>
                <CopyField
                  id="webdav-address"
                  label="Address"
                  value={address}
                />
                {config.username ? (
                  <CopyField
                    id="webdav-username"
                    label="Username"
                    value={config.username}
                  />
                ) : null}
                {password ? (
                  <CopyField
                    id="webdav-password"
                    label="Password"
                    value={password}
                  />
                ) : null}
                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldDescription>
                      {password
                        ? "Copy it now: it isn't shown again."
                        : config.has_password
                          ? "A password is set. Making a new one signs out every device using the old one."
                          : "Make a password to sign in. It's separate from your Athena password."}
                    </FieldDescription>
                  </FieldContent>
                  <Button
                    variant="outline"
                    disabled={saving || !user.is_admin}
                    onClick={() => void generate()}
                  >
                    <KeyRoundIcon />
                    {config.has_password ? "New password" : "Make password"}
                  </Button>
                </Field>
                {plainHttp ? (
                  <Alert>
                    <AlertTitle>Not encrypted</AlertTitle>
                    <AlertDescription>
                      Athena is open over plain HTTP, so the WebDAV password and
                      files cross the network unencrypted. Use it on a network
                      you trust, or put Athena behind HTTPS.
                    </AlertDescription>
                  </Alert>
                ) : null}
                <div className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                  <p>
                    <span className="font-medium text-foreground">macOS:</span>{" "}
                    Finder → Go → Connect to Server, then the address.
                  </p>
                  <p>
                    <span className="font-medium text-foreground">
                      Windows:
                    </span>{" "}
                    File Explorer → This PC → Map network drive, then the
                    address. Over plain HTTP Windows only signs in after setting{" "}
                    <code>BasicAuthLevel</code> to 2 under{" "}
                    <code>
                      HKLM\SYSTEM\CurrentControlSet\Services\WebClient\Parameters
                    </code>{" "}
                    and restarting the WebClient service.
                  </p>
                  <p>
                    <span className="font-medium text-foreground">Linux:</span>{" "}
                    in Files (GNOME) or Dolphin, connect to{" "}
                    <code>{address.replace(/^http/, "dav")}</code>.
                  </p>
                </div>
              </>
            ) : null}
          </FieldGroup>
        )}
      </CardContent>
    </Card>
  )
}
