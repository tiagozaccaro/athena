"use client"

import * as React from "react"
import { CircleAlertIcon } from "lucide-react"
import { Area, AreaChart, YAxis } from "recharts"

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Badge } from "@workspace/ui/components/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@workspace/ui/components/chart"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@workspace/ui/components/toggle-group"

import {
  type StatsSample,
  useHostStats,
} from "@/components/dashboard/host-stats-provider"
import {
  formatBytes,
  formatClock,
  formatPercent,
  formatRate,
} from "@/lib/format"

type Range = "5m" | "1h"
const RANGE_SECONDS: Record<Range, number> = { "5m": 300, "1h": 3600 }
const MAX_POINTS = 150

type Point = { t: number } & Record<string, number>

/** The samples in the range, averaged into at most MAX_POINTS buckets. */
function series(
  history: StatsSample[],
  range: Range,
  pick: (s: StatsSample) => Record<string, number>
): Point[] {
  if (history.length === 0) return []
  const since = history[history.length - 1]!.t - RANGE_SECONDS[range]
  const shown = history.filter((s) => s.t > since)
  const size = Math.max(1, Math.ceil(shown.length / MAX_POINTS))
  const points: Point[] = []
  for (let i = 0; i < shown.length; i += size) {
    const bucket = shown.slice(i, i + size)
    const sums: Record<string, number> = {}
    for (const s of bucket) {
      for (const [k, v] of Object.entries(pick(s))) sums[k] = (sums[k] ?? 0) + v
    }
    const point: Point = { t: bucket[bucket.length - 1]!.t } as Point
    for (const [k, v] of Object.entries(sums)) point[k] = v / bucket.length
    points.push(point)
  }
  return points
}

function Sparkline({
  data,
  config,
  format,
  max,
}: {
  data: Point[]
  config: ChartConfig
  format: (value: number) => string
  max?: number
}) {
  const keys = Object.keys(config)
  return (
    <ChartContainer config={config} className="aspect-auto h-16 w-full">
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <YAxis hide domain={[0, max ?? "auto"]} />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              indicator="line"
              labelFormatter={(_, payload) => {
                const t = (payload?.[0]?.payload as Point | undefined)?.t
                return t ? formatClock(t) : null
              }}
              formatter={(value, name) => (
                <div className="flex w-full items-center justify-between gap-4">
                  <span className="text-muted-foreground">
                    {config[name as string]?.label ?? name}
                  </span>
                  <span className="font-mono tabular-nums">
                    {format(Number(value))}
                  </span>
                </div>
              )}
            />
          }
        />
        {keys.map((key) => (
          <Area
            key={key}
            dataKey={key}
            type="monotone"
            isAnimationActive={false}
            stroke={`var(--color-${key})`}
            fill={`var(--color-${key})`}
            fillOpacity={0.2}
            strokeWidth={1.5}
          />
        ))}
      </AreaChart>
    </ChartContainer>
  )
}

function StatCard({
  label,
  value,
  badge,
  footer,
  children,
}: {
  label: string
  value: React.ReactNode
  badge?: React.ReactNode
  footer: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card className="@container/card gap-3">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="truncate text-2xl font-semibold tabular-nums">
          {value}
        </CardTitle>
        {badge ? <CardAction>{badge}</CardAction> : null}
      </CardHeader>
      <CardContent className="px-0 sm:px-0">{children}</CardContent>
      <CardFooter className="min-h-5 truncate text-sm text-muted-foreground">
        {footer}
      </CardFooter>
    </Card>
  )
}

const cpuConfig = {
  cpu: { label: "CPU", color: "var(--chart-1)" },
} satisfies ChartConfig
const memConfig = {
  mem: { label: "Used", color: "var(--chart-2)" },
} satisfies ChartConfig
const netConfig = {
  rx: { label: "Download", color: "var(--chart-3)" },
  tx: { label: "Upload", color: "var(--chart-4)" },
} satisfies ChartConfig
const diskConfig = {
  read: { label: "Read", color: "var(--chart-1)" },
  write: { label: "Write", color: "var(--chart-5)" },
} satisfies ChartConfig

/** CPU, memory, network and disk activity cards with sparklines, fed by HostStatsProvider. */
export function HostStatsCards() {
  const { status, host, history, live } = useHostStats()
  const [range, setRange] = React.useState<Range>("5m")

  if (status === "error") {
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>Live stats are unavailable</AlertTitle>
        <AlertDescription>
          The server didn&apos;t return host statistics.
        </AlertDescription>
      </Alert>
    )
  }

  const latest = host?.latest
  if (!host || !latest) {
    return (
      <div className="grid gap-4 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-44 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  const memPercent = (latest.mem_used / latest.mem_total) * 100
  const hasDiskIo = latest.disk_read !== null && latest.disk_write !== null
  const cores =
    host.cpu_count_physical && host.cpu_count_physical !== host.cpu_count
      ? `${host.cpu_count_physical} cores · ${host.cpu_count} threads`
      : `${host.cpu_count} cores`

  return (
    <section aria-label="Live host stats" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-medium">System</h2>
          <Badge variant={live ? "secondary" : "outline"}>
            <span
              aria-hidden
              className={`size-1.5 rounded-full ${live ? "animate-pulse bg-primary" : "bg-muted-foreground"}`}
            />
            {live ? "Live" : "Reconnecting"}
          </Badge>
        </div>
        <ToggleGroup
          aria-label="Chart range"
          value={[range]}
          onValueChange={(value: string[]) =>
            value[0] && setRange(value[0] as Range)
          }
          variant="outline"
          size="sm"
          spacing={0}
        >
          <ToggleGroupItem value="5m">5 min</ToggleGroupItem>
          <ToggleGroupItem value="1h">1 hour</ToggleGroupItem>
        </ToggleGroup>
      </div>

      <div className="grid gap-4 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        <StatCard
          label="CPU"
          value={formatPercent(latest.cpu_percent)}
          badge={
            latest.cpu_temp !== null ? (
              <Badge variant="outline">{Math.round(latest.cpu_temp)} °C</Badge>
            ) : undefined
          }
          footer={
            host.load_avg ? `${cores} · load ${host.load_avg.join(" ")}` : cores
          }
        >
          <Sparkline
            data={series(history, range, (s) => ({ cpu: s.cpu_percent }))}
            config={cpuConfig}
            format={formatPercent}
            max={100}
          />
        </StatCard>

        <StatCard
          label="Memory"
          value={formatPercent(memPercent)}
          badge={
            <Badge variant="outline">{formatBytes(latest.mem_total)}</Badge>
          }
          footer={
            `${formatBytes(latest.mem_used)} used` +
            (latest.swap_total > 0
              ? ` · swap ${formatBytes(latest.swap_used)}`
              : "")
          }
        >
          <Sparkline
            data={series(history, range, (s) => ({
              mem: (s.mem_used / s.mem_total) * 100,
            }))}
            config={memConfig}
            format={formatPercent}
            max={100}
          />
        </StatCard>

        <StatCard
          label="Network"
          value={`↓ ${formatRate(latest.net_rx)}`}
          footer={`↑ ${formatRate(latest.net_tx)}`}
        >
          <Sparkline
            data={series(history, range, (s) => ({
              rx: s.net_rx,
              tx: s.net_tx,
            }))}
            config={netConfig}
            format={formatRate}
          />
        </StatCard>

        {hasDiskIo ? (
          <StatCard
            label="Disk activity"
            value={`R ${formatRate(latest.disk_read ?? 0)}`}
            footer={`W ${formatRate(latest.disk_write ?? 0)}`}
          >
            <Sparkline
              data={series(history, range, (s) => ({
                read: s.disk_read ?? 0,
                write: s.disk_write ?? 0,
              }))}
              config={diskConfig}
              format={formatRate}
            />
          </StatCard>
        ) : null}
      </div>
    </section>
  )
}
