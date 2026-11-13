"use client"

import { HardDriveIcon, ThermometerIcon } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "@workspace/ui/components/progress"
import { Skeleton } from "@workspace/ui/components/skeleton"

import { useHostStats } from "@/components/dashboard/host-stats-provider"
import { formatBytes } from "@/lib/format"

/** Usage per disk the user manages (system volumes and snaps are filtered by the server). */
export function StorageCard() {
  const { host } = useHostStats()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HardDriveIcon className="size-4 text-muted-foreground" />
          Storage
        </CardTitle>
        <CardDescription>Space used on each disk</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!host ? (
          <Skeleton className="h-10 w-full" />
        ) : host.disks.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No disks reported yet.
          </p>
        ) : (
          host.disks.map((disk) => (
            <Progress key={disk.mountpoint} value={disk.percent}>
              <ProgressLabel className="min-w-0 truncate" title={disk.device}>
                {disk.mountpoint}
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {disk.fstype}
                </span>
              </ProgressLabel>
              <ProgressValue>
                {() =>
                  `${formatBytes(disk.used)} of ${formatBytes(disk.total)}`
                }
              </ProgressValue>
            </Progress>
          ))
        )}
      </CardContent>
    </Card>
  )
}

/** Hardware sensors. Rendered only on hosts that report them (Linux). */
export function TemperaturesCard() {
  const { host } = useHostStats()
  const temps = host?.temperatures
  if (!temps || temps.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ThermometerIcon className="size-4 text-muted-foreground" />
          Temperatures
        </CardTitle>
        <CardDescription>Hardware sensors</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2 text-sm">
          {temps.map((t) => {
            const hot =
              t.high !== null && t.high !== undefined && t.current >= t.high
            return (
              <div key={t.label} className="contents">
                <dt className="truncate text-muted-foreground">{t.label}</dt>
                <dd
                  className={`tabular-nums ${hot ? "font-medium text-destructive" : ""}`}
                >
                  {t.current.toFixed(0)} °C
                </dd>
              </div>
            )
          })}
        </dl>
      </CardContent>
    </Card>
  )
}
