"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { isAllowed, useCapabilities } from "@/components/capabilities-provider"
import { isActive, type NavItem } from "@/components/nav"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@workspace/ui/components/sidebar"

// The block's "Quick Create" button becomes "Add app" when the store lands (M3).
export function NavMain({ items }: { items: NavItem[] }) {
  const pathname = usePathname()
  const { manifest } = useCapabilities()
  return (
    <SidebarGroup>
      <SidebarGroupContent className="flex flex-col gap-2">
        <SidebarMenu>
          {items
            .filter((item) =>
              isAllowed(manifest, item.capability, item.showWhenUnavailable)
            )
            .map((item) => {
              const active = isActive(item, pathname)
              return (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    tooltip={item.title}
                    isActive={active}
                    render={<Link href={item.url} />}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
