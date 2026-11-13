import type { LucideIcon } from "lucide-react"
import { BoxIcon, CircleHelpIcon, LayoutDashboardIcon } from "lucide-react"

export type NavItem = {
  title: string
  url: string
  icon: LucideIcon
  /**
   * Capability id from the server's manifest (M1). Items whose capability is
   * missing on this host are hidden. Undefined means always shown.
   */
  capability?: string
  /**
   * Also show the item when the capability is stopped or not installed (but relevant
   * to this OS), so the page can offer Start or setup instructions.
   */
  showWhenUnavailable?: boolean
  external?: boolean
}

// Sections are added here as their milestones land (Apps, Store, Packages, Files,
// Cloud, Terminal, Assistant, Settings), so the sidebar never links to a missing page.
export const navMain: NavItem[] = [
  { title: "Dashboard", url: "/", icon: LayoutDashboardIcon },
  {
    title: "Containers",
    url: "/containers/",
    icon: BoxIcon,
    capability: "containers",
    showWhenUnavailable: true,
  },
]

/** True when `pathname` is the item's page or below it ("/" only matches itself). */
export function isActive(item: NavItem, pathname: string): boolean {
  if (item.url === "/") return pathname === "/"
  return pathname.startsWith(item.url.replace(/\/$/, ""))
}

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
  const match = navMain.find((item) => isActive(item, pathname))
  return match?.title ?? "Athena"
}
