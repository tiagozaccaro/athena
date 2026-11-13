"use client"

import * as React from "react"
import Link from "next/link"
import { ChevronDownIcon, ExternalLinkIcon, InfoIcon } from "lucide-react"

import { api, errorMessage, type Schemas } from "@workspace/api-client"
import { CodeEditor } from "@workspace/ui/components/athena/code-editor"
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
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@workspace/ui/components/collapsible"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Skeleton } from "@workspace/ui/components/skeleton"

import { AppIcon } from "@/components/store/app-icon"
import { InstallForm } from "@/components/store/install-form"

type Detail = Schemas["StoreAppDetail"]

export function StoreAppView({ catalog, id }: { catalog: string; id: string }) {
  const [app, setApp] = React.useState<Detail | null>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    api
      .GET("/api/store/apps/{catalog}/{app_id}", {
        params: { path: { catalog, app_id: id } },
      })
      .then(({ data, error: err }) => {
        if (data) setApp(data)
        else setError(errorMessage(err, "Couldn't load this app"))
      })
  }, [catalog, id])

  if (error) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyTitle>App not found</EmptyTitle>
          <EmptyDescription>{error}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  if (!app) return <Skeleton className="h-96 w-full" />

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_minmax(0,28rem)]">
      <div className="flex flex-col gap-6">
        <div className="flex items-start gap-4">
          <AppIcon title={app.title} icon={app.icon} className="size-16" />
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-semibold">{app.title}</h2>
            <p className="text-muted-foreground">{app.description}</p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Badge variant="outline" className="capitalize">
                {app.category}
              </Badge>
              {app.homepage ? (
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto px-0"
                  render={
                    <a href={app.homepage} target="_blank" rel="noreferrer" />
                  }
                >
                  Website
                  <ExternalLinkIcon data-icon="inline-end" />
                </Button>
              ) : null}
            </div>
          </div>
        </div>

        {app.installed.length ? (
          <Alert>
            <InfoIcon />
            <AlertTitle>Already installed</AlertTitle>
            <AlertDescription>
              <span>
                As{" "}
                {app.installed.map((n, i) => (
                  <React.Fragment key={n}>
                    {i > 0 ? ", " : ""}
                    <Link
                      href={`/apps/view/?name=${encodeURIComponent(n)}`}
                      className="underline underline-offset-4"
                    >
                      {n}
                    </Link>
                  </React.Fragment>
                ))}
                . You can install another copy under a different name.
              </span>
            </AlertDescription>
          </Alert>
        ) : null}

        {app.notes ? (
          <Alert>
            <InfoIcon />
            <AlertTitle>Before you start</AlertTitle>
            <AlertDescription>{app.notes}</AlertDescription>
          </Alert>
        ) : null}

        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted-foreground">Images</dt>
          <dd className="font-mono text-xs break-all">
            {app.images.join(", ")}
          </dd>
          <dt className="text-muted-foreground">Platforms</dt>
          <dd>{app.platforms.join(", ")}</dd>
        </dl>

        <Collapsible>
          <CollapsibleTrigger
            render={
              <Button variant="outline" size="sm" className="group/compose" />
            }
          >
            View compose.yaml
            <ChevronDownIcon
              data-icon="inline-end"
              className="transition-transform group-data-panel-open/compose:rotate-180"
            />
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-3">
            <CodeEditor
              value={app.compose}
              readOnly
              aria-label={`${app.title} compose.yaml`}
              minHeight="10rem"
            />
          </CollapsibleContent>
        </Collapsible>
      </div>

      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Install</CardTitle>
          <CardDescription>
            Your answers are saved in the app&apos;s .env file on the server,
            next to its compose.yaml.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <InstallForm app={app} />
        </CardContent>
      </Card>
    </div>
  )
}
