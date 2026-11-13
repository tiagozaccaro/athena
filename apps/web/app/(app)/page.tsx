import { HostCapabilities } from "@/components/host-capabilities"
import { ServerOverview } from "@/components/server-overview"

export default function DashboardPage() {
  return (
    <div className="grid gap-4 md:gap-6 xl:grid-cols-2">
      <ServerOverview />
      <HostCapabilities />
    </div>
  )
}
