"use client"

import * as React from "react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Spinner } from "@workspace/ui/components/spinner"

type Integration = Schemas["IntegrationOut"]
type IntegrationIn = Schemas["IntegrationIn"]
type IntegrationKind = Schemas["IntegrationKindOut"]

type IntegrationEditing = {
  integration: Integration | null
  kinds: IntegrationKind[]
} | null

function slugId(name: string) {
  return (
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 64) || "integration"
  )
}

/** Add or edit a hosted integration. The token is stored encrypted on this server. */
export function IntegrationDialog({
  editing,
  onClose,
  onSaved,
}: {
  editing: IntegrationEditing
  onClose: () => void
  onSaved: (integration: Integration) => void
}) {
  if (!editing) return null
  const { integration: existing, kinds } = editing
  const isHttp = React.useMemo(
    () =>
      (existing?.transport as { type: string } | undefined)?.type === "http",
    [existing]
  )
  const [selectedKind, setSelectedKind] =
    React.useState<IntegrationKind | null>(
      existing ? (kinds.find((k) => k.id === existing.kind) ?? null) : null
    )
  // When editing, the kind is fixed; when adding, the user picks it.
  const kindFixed = !!existing
  const [name, setName] = React.useState(existing?.name ?? "")
  const [transportType, setTransportType] = React.useState<"stdio" | "http">(
    isHttp ? "http" : "stdio"
  )
  const [command, setCommand] = React.useState("")
  const [args, setArgs] = React.useState("")
  const [url, setUrl] = React.useState("")
  const [tokenTarget, setTokenTarget] = React.useState("")
  const [token, setToken] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    const transport = existing?.transport as
      | { type: string; command?: string; args?: string[]; url?: string }
      | undefined
    setName(existing?.name ?? "")
    setSelectedKind(
      existing ? (kinds.find((k) => k.id === existing.kind) ?? null) : null
    )
    setTransportType(isHttp ? "http" : "stdio")
    setCommand(transport?.command ?? "")
    setArgs(Array.isArray(transport?.args) ? transport.args.join(", ") : "")
    setUrl(transport?.url ?? "")
    setTokenTarget(
      isHttp ? (existing?.token_header ?? "") : (existing?.token_env ?? "")
    )
    setToken("")
    setError(null)
  }, [existing, kinds, isHttp])

  async function save(e: React.FormEvent) {
    e.preventDefault()
    const kind = kindFixed ? existing?.kind : selectedKind?.id
    if (!kind) return
    setSaving(true)
    setError(null)

    let transport: IntegrationIn["transport"]
    let token_env: string | undefined
    let token_header: string | undefined
    if (transportType === "stdio") {
      transport = {
        type: "stdio",
        command: command.trim(),
        args: args
          .split(",")
          .map((a) => a.trim())
          .filter(Boolean),
      }
      token_env = tokenTarget.trim() || undefined
    } else {
      transport = { type: "http", url: url.trim() }
      token_header = tokenTarget.trim() || undefined
    }

    const body: IntegrationIn = {
      id: existing?.id ?? slugId(name),
      kind,
      name: name.trim(),
      transport,
      ...(token_env !== undefined ? { token_env } : {}),
      ...(token_header !== undefined ? { token_header } : {}),
      ...(token ? { token } : {}),
    }

    const result = existing
      ? await api.PUT("/api/assistant/integrations/{integration_id}", {
          params: { path: { integration_id: existing.id } },
          body,
        })
      : await api.POST("/api/assistant/integrations", { body })
    setSaving(false)
    if (result.data) onSaved(result.data)
    else setError(errorMessage(result.error))
  }

  const stdioFields = (
    <>
      <Field>
        <FieldLabel htmlFor="integration-command">Command</FieldLabel>
        <Input
          id="integration-command"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="e.g. npx"
          required
        />
        <FieldDescription>
          The program that runs the MCP server, e.g. <code>npx</code> or{" "}
          <code>uvx</code>.
        </FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor="integration-args">Arguments</FieldLabel>
        <Input
          id="integration-args"
          value={args}
          onChange={(e) => setArgs(e.target.value)}
          placeholder="e.g. -y @modelcontextprotocol/server-github@latest"
        />
        <FieldDescription>
          Comma-separated arguments; no shell is used.
        </FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor="integration-token-env">
          Token environment variable
        </FieldLabel>
        <Input
          id="integration-token-env"
          value={tokenTarget}
          onChange={(e) => setTokenTarget(e.target.value)}
          placeholder="e.g. GITHUB_PERSONAL_ACCESS_TOKEN"
        />
        <FieldDescription>
          The env var that receives the decrypted token on each turn.
        </FieldDescription>
      </Field>
    </>
  )

  const httpFields = (
    <>
      <Field>
        <FieldLabel htmlFor="integration-url">URL</FieldLabel>
        <Input
          id="integration-url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="e.g. https://slack.example.com/mcp"
          required
        />
        <FieldDescription>
          The server's streamable-HTTP MCP endpoint.
        </FieldDescription>
      </Field>
      <Field>
        <FieldLabel htmlFor="integration-token-header">Token header</FieldLabel>
        <Input
          id="integration-token-header"
          value={tokenTarget}
          onChange={(e) => setTokenTarget(e.target.value)}
          placeholder="e.g. Authorization"
        />
        <FieldDescription>
          The HTTP header that receives the decrypted token on each request.
        </FieldDescription>
      </Field>
    </>
  )

  return (
    <Dialog open={true} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-lg">
        <form onSubmit={save} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>
              {existing ? `Edit ${existing.name}` : "Add integration"}
            </DialogTitle>
            <DialogDescription>
              The token is stored encrypted on this server and never sent back
              to the browser. Leave the token empty when editing to keep the
              stored value.
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="integration-kind">Integration</FieldLabel>
              <Select
                id="integration-kind"
                value={selectedKind?.id ?? ""}
                disabled={kindFixed}
                onValueChange={(v) => {
                  const picked = kinds.find((k) => k.id === v)
                  setSelectedKind(picked ?? null)
                }}
              >
                <SelectTrigger id="integration-kind-trigger" className="w-full">
                  <SelectValue
                    placeholder={
                      kindFixed
                        ? (selectedKind?.label ?? "")
                        : "Pick an integration"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {kinds.map((k) => (
                    <SelectItem key={k.id} value={k.id}>
                      {k.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {kindFixed ? (
                <FieldDescription>
                  The kind can't be changed after creation; remove and re-add to
                  pick another.
                </FieldDescription>
              ) : null}
            </Field>
            {error ? <FieldError>{error}</FieldError> : null}
            <Field>
              <FieldLabel htmlFor="integration-name">Name</FieldLabel>
              <Input
                id="integration-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={64}
                required
              />
              <FieldDescription>
                Shown when the integration is listed.
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="integration-transport-type">
                Transport
              </FieldLabel>
              <div className="flex gap-2">
                <Button
                  role="radio"
                  aria-checked={transportType === "stdio"}
                  onClick={() => setTransportType("stdio")}
                  variant={transportType === "stdio" ? "default" : "outline"}
                  size="sm"
                >
                  Stdio (command)
                </Button>
                <Button
                  role="radio"
                  aria-checked={transportType === "http"}
                  onClick={() => setTransportType("http")}
                  variant={transportType === "http" ? "default" : "outline"}
                  size="sm"
                >
                  HTTP (URL)
                </Button>
              </div>
            </Field>
            {transportType === "stdio" ? stdioFields : httpFields}
            <Field>
              <FieldLabel htmlFor="integration-token">Token</FieldLabel>
              <Input
                id="integration-token"
                type="password"
                autoComplete="new-password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="API token or OAuth access token"
              />
              <FieldDescription>
                Left empty when editing, the stored token is kept unchanged.
              </FieldDescription>
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving || !selectedKind}>
              {saving ? <Spinner /> : null}
              {existing ? "Save" : "Add"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
