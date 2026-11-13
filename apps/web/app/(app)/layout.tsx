import { AppSidebar } from "@/components/app-sidebar"
import { AuthProvider } from "@/components/auth-provider"
import { CapabilitiesProvider } from "@/components/capabilities-provider"
import { SiteHeader } from "@/components/site-header"
import { SidebarInset, SidebarProvider } from "@workspace/ui/components/sidebar"

// App shell from the shadcn dashboard-01 block (docs/mvp-design.md §5.2). Every
// signed-in page lives under this layout; /setup and /login are in app/(auth).
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <CapabilitiesProvider>
        <SidebarProvider
          style={
            {
              "--sidebar-width": "calc(var(--spacing) * 72)",
              "--header-height": "calc(var(--spacing) * 12)",
            } as React.CSSProperties
          }
        >
          <AppSidebar variant="inset" />
          <SidebarInset>
            <SiteHeader />
            <div className="@container/main flex flex-1 flex-col gap-4 p-4 md:gap-6 md:p-6">
              {children}
            </div>
          </SidebarInset>
        </SidebarProvider>
      </CapabilitiesProvider>
    </AuthProvider>
  )
}
