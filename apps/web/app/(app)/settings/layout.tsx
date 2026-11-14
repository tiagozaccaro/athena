"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { Button } from "@workspace/ui/components/button"

const SECTIONS = [
  { title: "Appearance", url: "/settings/appearance/" },
  { title: "Account", url: "/settings/account/" },
  { title: "System", url: "/settings/system/" },
  { title: "AI", url: "/settings/ai/" },
]

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <nav aria-label="Settings" className="flex flex-wrap gap-1">
        {SECTIONS.map((s) => {
          const active = pathname.startsWith(s.url.replace(/\/$/, ""))
          return (
            <Button
              key={s.url}
              variant={active ? "secondary" : "ghost"}
              size="sm"
              aria-current={active ? "page" : undefined}
              render={<Link href={s.url} />}
            >
              {s.title}
            </Button>
          )
        })}
      </nav>
      <div className="max-w-3xl">{children}</div>
    </div>
  )
}
