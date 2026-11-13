"use client"

import {
  BoxIcon,
  CloudIcon,
  FolderIcon,
  PackageIcon,
  RefreshCwIcon,
  Share2Icon,
  SquareTerminalIcon,
  type LucideIcon,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@workspace/ui/components/item"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"

import {
  type Capability,
  useCapabilities,
} from "@/components/capabilities-provider"

const STATUS: Record<
  Capability["status"],
  { label: string; variant: "secondary" | "outline" | "destructive" }
> = {
  ready: { label: "Ready", variant: "secondary" },
  stopped: { label: "Stopped", variant: "outline" },
  missing: { label: "Not installed", variant: "outline" },
  unsupported: { label: "Unsupported", variant: "outline" },
  needs_privilege: { label: "Needs root", variant: "destructive" },
}

function iconFor(id: string): LucideIcon {
  if (id === "containers") return BoxIcon
  if (id.startsWith("packages.")) return PackageIcon
  if (id.startsWith("terminal.")) return SquareTerminalIcon
  if (id.startsWith("cloud.")) return CloudIcon
  if (id.startsWith("shares.")) return Share2Icon
  return FolderIcon
}

/**
 * Package managers that aren't installed are left out entirely. The host only ever
 * shows what it has. Other capabilities stay visible when missing, because they can
 * be set up.
 */
function visible(c: Capability): boolean {
  return !(c.id.startsWith("packages.") && c.status === "missing")
}

export function HostCapabilities() {
  const { manifest, error, refreshing, refresh } = useCapabilities()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Capabilities</CardTitle>
        <CardDescription>
          What Athena found on this host. Features appear only where they can
          work.
        </CardDescription>
        <CardAction>
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={refreshing}
          >
            {refreshing ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <RefreshCwIcon data-icon="inline-start" />
            )}
            Re-detect
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {error && !manifest ? (
          <p className="text-sm text-muted-foreground">
            Couldn&apos;t load capabilities: {error}
          </p>
        ) : !manifest ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : (
          <ItemGroup>
            {manifest.capabilities.filter(visible).map((c) => {
              const Icon = iconFor(c.id)
              const status = STATUS[c.status]
              return (
                <Item key={c.id} size="sm">
                  <ItemMedia variant="icon">
                    <Icon />
                  </ItemMedia>
                  <ItemContent>
                    <ItemTitle>
                      {c.label}
                      {c.provider && c.provider !== "builtin" ? (
                        <span className="font-normal text-muted-foreground">
                          · {c.provider}
                        </span>
                      ) : null}
                    </ItemTitle>
                    {c.detail ? (
                      <ItemDescription>{c.detail}</ItemDescription>
                    ) : null}
                  </ItemContent>
                  <Badge variant={status.variant}>{status.label}</Badge>
                </Item>
              )
            })}
          </ItemGroup>
        )}
      </CardContent>
    </Card>
  )
}
