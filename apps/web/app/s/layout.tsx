import type { Metadata } from "next"
import { ServerIcon } from "lucide-react"

export const metadata: Metadata = {
  title: "Shared with you",
  // The address is the secret; keep it out of other sites' logs.
  referrer: "no-referrer",
  robots: { index: false, follow: false },
}

// /s/<token>: a share link's page. Outside the app shell and needs no session.
export default function ShareLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-svh flex-col items-center bg-muted px-4 py-6 md:p-10">
      <div className="flex w-full max-w-3xl flex-col gap-6">
        <div className="flex items-center gap-2 self-center font-medium">
          <div className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ServerIcon className="size-4" />
          </div>
          Athena
        </div>
        {children}
      </div>
    </div>
  )
}
