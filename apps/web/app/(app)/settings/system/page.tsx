import { SystemForm } from "@/components/settings/system-form"
import { WebDavCard } from "@/components/settings/webdav-card"

export default function SystemSettingsPage() {
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <SystemForm />
      <WebDavCard />
    </div>
  )
}
