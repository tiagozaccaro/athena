"use client"

import * as React from "react"
import {
  AlertTriangleIcon,
  CopyIcon,
  DownloadIcon,
  EyeIcon,
  EyeOffIcon,
  PlayIcon,
  RotateCcwIcon,
  SquareIcon,
} from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@workspace/ui/components/input-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Switch } from "@workspace/ui/components/switch"
import { toast } from "@workspace/ui/components/toast"

import { useAuth } from "@/components/auth-provider"
import { useCapability } from "@/components/capabilities-provider"
import { JobDialog } from "@/components/job-dialog"
import { patchSystemSettings } from "@/components/settings/system-settings"
import { copyText } from "@/lib/clipboard"

type TunnelProvider = "cloudflare" | "tailscale" | "ngrok"
type SystemSettings = Schemas["SystemSettings"]
type TunnelStatus = Schemas["TunnelStatusResponse"]
type Job = Schemas["JobOut"]
type Config = Record<string, unknown>

const PROVIDER_LABELS: Record<TunnelProvider, string> = {
  cloudflare: "Cloudflare Tunnel",
  tailscale: "Tailscale Funnel",
  ngrok: "ngrok",
}

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

function SecretInput({
  id,
  label,
  value,
  onChange,
  disabled,
  placeholder,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  placeholder?: string
}) {
  const [show, setShow] = React.useState(false)
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <InputGroup>
        <InputGroupInput
          id={id}
          type={show ? "text" : "password"}
          autoComplete="off"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={placeholder}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            size="icon-xs"
            aria-label={show ? `Hide ${label}` : `Show ${label}`}
            onClick={() => setShow(!show)}
          >
            {show ? <EyeOffIcon /> : <EyeIcon />}
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </Field>
  )
}

function TextField({
  id,
  label,
  value,
  onChange,
  disabled,
  placeholder,
  description,
}: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  placeholder?: string
  description: string
}) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
      />
      <FieldDescription>{description}</FieldDescription>
    </Field>
  )
}

function ProviderConfigForm({
  provider,
  config,
  secretsSet,
  onChange,
  disabled,
}: {
  provider: TunnelProvider
  config: Config
  /** Secret keys with a stored value. The server never sends secrets back. */
  secretsSet: string[]
  onChange: (config: Config) => void
  disabled: boolean
}) {
  const set = (key: string) => (value: unknown) =>
    onChange({ ...config, [key]: value })
  const str = (key: string) => (config[key] as string | undefined) ?? ""
  const secretPlaceholder = (key: string, empty: string) =>
    secretsSet.includes(key) ? "Saved. Type a new value to replace it" : empty

  if (provider === "cloudflare") {
    const quickTunnel = (config.quick_tunnel as boolean | undefined) ?? true
    return (
      <>
        <Field orientation="horizontal">
          <FieldContent>
            <FieldLabel htmlFor="cf-quick">Quick tunnel</FieldLabel>
            <FieldDescription>
              A random trycloudflare.com address that needs no account. It
              changes every time the tunnel starts.
            </FieldDescription>
          </FieldContent>
          <Switch
            id="cf-quick"
            checked={quickTunnel}
            disabled={disabled}
            onCheckedChange={set("quick_tunnel")}
          />
        </Field>
        {!quickTunnel && (
          <>
            <SecretInput
              id="cf-api-token"
              label="API token"
              value={str("api_token")}
              onChange={set("api_token")}
              disabled={disabled}
              placeholder={secretPlaceholder(
                "api_token",
                "A Cloudflare API token with Tunnel permissions"
              )}
            />
            <TextField
              id="cf-tunnel-name"
              label="Tunnel name"
              value={str("tunnel_name")}
              onChange={set("tunnel_name")}
              disabled={disabled}
              placeholder="my-tunnel"
              description="The named tunnel in your Cloudflare account."
            />
            <TextField
              id="cf-domain"
              label="Custom domain (optional)"
              value={str("domain")}
              onChange={set("domain")}
              disabled={disabled}
              placeholder="athena.example.com"
              description="Needs a DNS record pointing at the tunnel."
            />
          </>
        )}
      </>
    )
  }

  if (provider === "tailscale") {
    return (
      <Field>
        <FieldLabel htmlFor="ts-tailnet">Tailnet</FieldLabel>
        <Input
          id="ts-tailnet"
          readOnly
          value={str("tailnet_name") || "Detected automatically"}
        />
        <FieldDescription>
          Set with <code>tailscale up</code> on this server.
        </FieldDescription>
      </Field>
    )
  }

  return (
    <>
      <SecretInput
        id="ngrok-auth-token"
        label="Auth token"
        value={str("auth_token")}
        onChange={set("auth_token")}
        disabled={disabled}
        placeholder={secretPlaceholder("auth_token", "Your ngrok auth token")}
      />
      <TextField
        id="ngrok-domain"
        label="Custom domain (optional)"
        value={str("domain")}
        onChange={set("domain")}
        disabled={disabled}
        placeholder="athena.example.com"
        description="Needs a paid ngrok plan."
      />
      <TextField
        id="ngrok-subdomain"
        label="Subdomain (optional)"
        value={str("subdomain")}
        onChange={set("subdomain")}
        disabled={disabled}
        placeholder="my-athena"
        description="Needs a paid ngrok plan."
      />
      <Alert>
        <AlertTriangleIcon />
        <AlertTitle>Free plan limits</AlertTitle>
        <AlertDescription>
          One tunnel, 40 connections a minute, and a new random address each
          session.
        </AlertDescription>
      </Alert>
    </>
  )
}

function StatusBadge({ status }: { status: TunnelStatus | null }) {
  if (!status) return <Skeleton className="h-5 w-20" />
  if (status.running) return <Badge>Running</Badge>
  switch (status.capability_status) {
    case "stopped":
      return <Badge variant="secondary">Stopped</Badge>
    case "not_installed":
      return <Badge variant="destructive">Not installed</Badge>
    default:
      return <Badge variant="outline">Not set up</Badge>
  }
}

const sameJson = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b)

export function TunnelCard() {
  const { user } = useAuth()
  // Call each hook on every render: `a || b || c` skipped calls and broke
  // React's rules of hooks.
  const cloudflare = useCapability("tunnel.cloudflare")
  const tailscale = useCapability("tunnel.tailscale")
  const ngrok = useCapability("tunnel.ngrok")
  const hasTunnelCapability = Boolean(cloudflare || tailscale || ngrok)

  const [status, setStatus] = React.useState<TunnelStatus | null>(null)
  const [settings, setSettings] = React.useState<SystemSettings | null>(null)
  const [saving, setSaving] = React.useState(false)
  const [job, setJob] = React.useState<Job | null>(null)
  // Typed fields stay a draft until Save: typing used to send a request per
  // keystroke and lock the field while each one ran.
  const [config, setConfig] = React.useState<Config>({})
  const [port, setPort] = React.useState("8420")

  const refreshStatus = React.useCallback(async () => {
    const { data } = await api.GET("/api/tunnel/status")
    if (data) setStatus(data)
  }, [])

  const loadDraft = (data: SystemSettings) => {
    setConfig(data.tunnel_config ?? {})
    setPort(String(data.tunnel_port ?? 8420))
  }

  React.useEffect(() => {
    void api.GET("/api/settings/system").then(({ data }) => {
      if (!data) return
      setSettings(data)
      loadDraft(data)
    })
    void refreshStatus()
  }, [refreshStatus])

  if (!hasTunnelCapability) return null

  const canEdit = user.is_admin && !saving
  const provider = (settings?.tunnel_provider as TunnelProvider) ?? "cloudflare"
  const portNumber = Number(port)
  const portValid =
    Number.isInteger(portNumber) && portNumber >= 1 && portNumber <= 65535
  const dirty =
    settings !== null &&
    (!sameJson(config, settings.tunnel_config ?? {}) ||
      portNumber !== (settings.tunnel_port ?? 8420))

  async function save(
    next: Partial<SystemSettings>,
    message: string
  ): Promise<SystemSettings | null> {
    if (!settings) return null
    setSaving(true)
    const { data, error } = await patchSystemSettings(next)
    setSaving(false)
    if (!data) {
      toast.add({
        type: "error",
        title: "Couldn't save",
        description: errorMessage(error),
      })
      return null
    }
    setSettings(data)
    toast.add({ type: "success", title: message })
    void refreshStatus()
    return data
  }

  async function saveDraft() {
    if (!portValid) return
    const data = await save(
      { tunnel_config: config, tunnel_port: portNumber },
      "Remote access settings saved"
    )
    // The server never returns secrets, so this also clears typed tokens and
    // shows their "Saved" placeholder instead.
    if (data) loadDraft(data)
  }

  async function runJob(
    request: Promise<{
      data?: { job_id?: string | null } | null
      error?: unknown
    }>,
    failure: string
  ) {
    const { data, error } = await request
    if (!data?.job_id) {
      toast.add({
        type: "error",
        title: failure,
        description: errorMessage(error),
      })
      return
    }
    const { data: jobData } = await api.GET("/api/jobs/{job_id}", {
      params: { path: { job_id: data.job_id } },
    })
    if (jobData) setJob(jobData)
  }

  async function changeAutoStart(enabled: boolean) {
    const saved = await save(
      { tunnel_auto_start: enabled },
      enabled
        ? "Remote access starts on boot"
        : "Remote access no longer starts on boot"
    )
    if (!saved) return
    await runJob(
      api.PUT("/api/tunnel/service", { params: { query: { enabled } } }),
      "Couldn't update the service"
    )
  }

  const running = status?.running ?? false
  const capabilityStatus = status?.capability_status ?? "missing"
  const needsInstall =
    capabilityStatus === "missing" || capabilityStatus === "not_installed"

  return (
    <Card>
      <CardHeader>
        <CardTitle>Remote access</CardTitle>
        <CardDescription>
          Reach Athena from anywhere through Cloudflare, Tailscale or ngrok,
          without opening ports on your router.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {settings === null ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <FieldGroup>
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor="tunnel-enabled">Remote access</FieldLabel>
                <FieldDescription>
                  Anyone with the address reaches your sign-in page, so use a
                  strong password.
                  {!user.is_admin && " Only admins can change this."}
                </FieldDescription>
              </FieldContent>
              <Switch
                id="tunnel-enabled"
                checked={settings.tunnel_enabled}
                disabled={!canEdit}
                onCheckedChange={(checked) =>
                  void save(
                    { tunnel_enabled: checked },
                    checked
                      ? "Remote access turned on"
                      : "Remote access turned off"
                  )
                }
              />
            </Field>

            {settings.tunnel_enabled && (
              <>
                <FieldSeparator />
                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldLabel htmlFor="tunnel-provider">Provider</FieldLabel>
                  </FieldContent>
                  <Select
                    value={provider}
                    onValueChange={(value) =>
                      value &&
                      void save(
                        { tunnel_provider: value },
                        `Using ${PROVIDER_LABELS[value as TunnelProvider]}`
                      )
                    }
                    disabled={!canEdit}
                  >
                    <SelectTrigger id="tunnel-provider" className="w-48">
                      <SelectValue>
                        {(value: TunnelProvider) => PROVIDER_LABELS[value]}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(PROVIDER_LABELS) as TunnelProvider[]).map(
                        (p) => (
                          <SelectItem key={p} value={p}>
                            {PROVIDER_LABELS[p]}
                          </SelectItem>
                        )
                      )}
                    </SelectContent>
                  </Select>
                </Field>

                <ProviderConfigForm
                  provider={provider}
                  config={config}
                  secretsSet={settings.tunnel_secrets_set ?? []}
                  onChange={setConfig}
                  disabled={!user.is_admin}
                />

                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldLabel htmlFor="tunnel-port">Local port</FieldLabel>
                    <FieldDescription>
                      The port Athena listens on, which the tunnel forwards to.
                    </FieldDescription>
                  </FieldContent>
                  <Input
                    id="tunnel-port"
                    inputMode="numeric"
                    value={port}
                    onChange={(e) => setPort(e.target.value)}
                    disabled={!user.is_admin}
                    aria-invalid={!portValid || undefined}
                    className="w-24"
                  />
                </Field>

                {dirty && (
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      onClick={() => loadDraft(settings)}
                    >
                      Discard
                    </Button>
                    <Button
                      onClick={() => void saveDraft()}
                      disabled={!canEdit || !portValid}
                    >
                      Save changes
                    </Button>
                  </div>
                )}

                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldLabel htmlFor="tunnel-auto-start">
                      Start on boot
                    </FieldLabel>
                    <FieldDescription>
                      {needsInstall
                        ? `Install ${PROVIDER_LABELS[provider]} first.`
                        : "Installs a system service that starts the tunnel with the server."}
                    </FieldDescription>
                  </FieldContent>
                  <Switch
                    id="tunnel-auto-start"
                    // Nothing can start on boot before the tool is installed.
                    checked={
                      !needsInstall && (settings.tunnel_auto_start ?? false)
                    }
                    disabled={!canEdit || needsInstall}
                    onCheckedChange={(checked) => void changeAutoStart(checked)}
                  />
                </Field>

                <FieldSeparator />

                <div className="flex flex-col gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">Status</span>
                    <StatusBadge status={status} />
                  </div>
                  {status?.public_url && (
                    <CopyField
                      id="tunnel-url"
                      label="Public address"
                      value={status.public_url}
                    />
                  )}
                  {status?.detail && (
                    <p className="text-sm text-muted-foreground">
                      {status.detail}
                    </p>
                  )}
                </div>
              </>
            )}
          </FieldGroup>
        )}
      </CardContent>
      {settings?.tunnel_enabled && (
        <CardFooter className="flex flex-wrap gap-2">
          {needsInstall ? (
            <Button
              variant="outline"
              disabled={!canEdit}
              onClick={() =>
                void runJob(
                  api.POST("/api/tunnel/install", { body: { provider } }),
                  "Couldn't install"
                )
              }
            >
              <DownloadIcon data-icon="inline-start" />
              Install {PROVIDER_LABELS[provider]}
            </Button>
          ) : running ? (
            <Button
              variant="destructive"
              disabled={!canEdit}
              onClick={() =>
                void runJob(
                  api.POST("/api/tunnel/stop"),
                  "Couldn't stop the tunnel"
                )
              }
            >
              <SquareIcon data-icon="inline-start" />
              Stop
            </Button>
          ) : (
            <Button
              disabled={!canEdit || dirty}
              title={dirty ? "Save your changes first" : undefined}
              onClick={() =>
                void runJob(
                  api.POST("/api/tunnel/start"),
                  "Couldn't start the tunnel"
                )
              }
            >
              <PlayIcon data-icon="inline-start" />
              Start
            </Button>
          )}
          <Button variant="ghost" onClick={() => void refreshStatus()}>
            <RotateCcwIcon data-icon="inline-start" />
            Refresh status
          </Button>
        </CardFooter>
      )}
      <JobDialog
        job={job}
        onClose={() => setJob(null)}
        onFinished={() => void refreshStatus()}
      />
    </Card>
  )
}
