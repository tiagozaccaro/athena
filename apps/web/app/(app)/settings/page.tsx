"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

// A static export can't redirect on the server, so /settings/ forwards in the browser.
export default function SettingsIndex() {
  const router = useRouter()
  React.useEffect(() => router.replace("/settings/appearance/"), [router])
  return null
}
