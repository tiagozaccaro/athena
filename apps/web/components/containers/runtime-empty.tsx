"use client"

import * as React from "react"
import { BoxIcon, PlayIcon, RefreshCwIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { Button } from "@workspace/ui/components/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Spinner } from "@workspace/ui/components/spinner"
import { toast } from "@workspace/ui/components/toast"

import {
  type Capability,
  useCapabilities,
} from "@/components/capabilities-provider"
import { JobDialog } from "@/components/job-dialog"

type Job = Schemas["JobOut"]

/** How to install a runtime on each OS (Windows is detect-only: docs/mvp-design.md §3). */
const SETUP: Record<string, { title: string; steps: string[] }> = {
  darwin: {
    title: "Install Colima",
    steps: ["brew install colima docker docker-compose", "colima start"],
  },
  linux: {
    title: "Install Docker Engine",
    steps: [
      "curl -fsSL https://get.docker.com | sudo sh",
      "sudo systemctl enable --now docker",
    ],
  },
  windows: {
    title: "Install a container runtime",
    steps: [
      "Docker Engine in WSL2: wsl --install, then install docker-ce inside the distro",
      "or Podman: winget install RedHat.Podman, then podman machine init; podman machine start",
      "or Rancher Desktop: winget install SUSE.RancherDesktop (choose the dockerd engine)",
    ],
  },
}

export function RuntimeEmpty({
  capability,
}: {
  capability: Capability | undefined
}) {
  const { manifest, refresh, refreshing } = useCapabilities()
  const [job, setJob] = React.useState<Job | null>(null)
  const [starting, setStarting] = React.useState(false)
  const canStart = capability?.actions.includes("start")
  const setup = SETUP[manifest?.os ?? "linux"]

  async function start() {
    setStarting(true)
    const { data, error } = await api.POST("/api/containers/runtime/start")
    setStarting(false)
    if (data) setJob(data)
    else
      toast.add({
        type: "error",
        title: "Couldn't start the runtime",
        description: errorMessage(error),
      })
  }

  const finished = React.useCallback(
    (ok: boolean) => {
      if (ok) {
        void refresh()
        toast.add({ type: "success", title: "Container runtime is running" })
      }
    },
    [refresh]
  )

  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <BoxIcon />
        </EmptyMedia>
        <EmptyTitle>
          {capability?.status === "stopped"
            ? `${capability.provider ?? "The container runtime"} isn't running`
            : "No container runtime"}
        </EmptyTitle>
        <EmptyDescription>
          {capability?.detail ??
            "Athena didn't find a container engine on this host."}
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        {canStart ? (
          <Button onClick={start} disabled={starting}>
            {starting ? (
              <Spinner data-icon="inline-start" />
            ) : (
              <PlayIcon data-icon="inline-start" />
            )}
            Start {capability?.provider}
          </Button>
        ) : setup ? (
          <div className="flex w-full flex-col gap-2 text-left">
            <p className="text-sm font-medium">{setup.title}</p>
            <pre className="rounded-lg border bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap">
              {setup.steps.join("\n")}
            </pre>
          </div>
        ) : null}
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
      </EmptyContent>
      <JobDialog job={job} onClose={() => setJob(null)} onFinished={finished} />
    </Empty>
  )
}
