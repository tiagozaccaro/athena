import type { Metadata } from "next"

import "@workspace/ui/globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { APPEARANCE_SCRIPT, DEFAULT_ATTRIBUTES } from "@/lib/appearance"
import { fontVariables } from "@/lib/fonts"
import { Toaster } from "@workspace/ui/components/toast"
import { TooltipProvider } from "@workspace/ui/components/tooltip"
import { cn } from "@workspace/ui/lib/utils"

export const metadata: Metadata = {
  title: { default: "Athena", template: "%s · Athena" },
  description: "Self-hosted home server dashboard",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn("font-sans antialiased", fontVariables)}
      {...DEFAULT_ATTRIBUTES}
    >
      <head>
        {/* Applies the saved base color, theme, fonts and radius before first paint
            (docs/mvp-design.md §5.4). next-themes injects its own script for dark mode. */}
        <script dangerouslySetInnerHTML={{ __html: APPEARANCE_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <TooltipProvider>{children}</TooltipProvider>
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
