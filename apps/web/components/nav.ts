import type { LucideIcon } from "lucide-react"
import { CircleHelpIcon, LayoutDashboardIcon } from "lucide-react"

export type NavItem = {
  title: string
  url: string
  icon: LucideIcon
  /**
   * Capability id from the server's manifest (M1). Items whose capability is
   * missing on this host are hidden. Undefined means always shown.
   */
  capability?: string
  external?: boolean
}

// Sections are added here as their milestones land (Apps, Store, Packages, Files,
// Cloud, Terminal, Assistant, Settings), so the sidebar never links to a missing page.
export const navMain: NavItem[] = [
  { title: "Dashboard", url: "/", icon: LayoutDashboardIcon },
]

export const navSecondary: NavItem[] = [
  {
    title: "Help",
    url: "https://github.com/tiagozaccaro/athena#readme",
    icon: CircleHelpIcon,
    external: true,
  },
]

/** Title for the header, from the nav item matching the current path. */
export function titleForPath(pathname: string): string {
  const match = navMain.find((item) =>
    item.url === "/" ? pathname === "/" : pathname.startsWith(item.url)
  )
  return match?.title ?? "Athena"
}
