import { HostStatsCards } from "@/components/dashboard/host-stats-cards"
import { HostStatsProvider } from "@/components/dashboard/host-stats-provider"
import {
  StorageCard,
  TemperaturesCard,
} from "@/components/dashboard/storage-card"
import { HostCapabilities } from "@/components/host-capabilities"
import { ServerOverview } from "@/components/server-overview"

export default function DashboardPage() {
  return (
    <HostStatsProvider>
      <HostStatsCards />
      <div className="grid gap-4 md:gap-6 xl:grid-cols-2">
        <StorageCard />
        <ServerOverview />
        <TemperaturesCard />
        <HostCapabilities />
      </div>
    </HostStatsProvider>
  )
}
