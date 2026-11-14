import {
  DM_Sans,
  EB_Garamond,
  Figtree,
  Geist,
  Geist_Mono,
  IBM_Plex_Sans,
  Instrument_Sans,
  Instrument_Serif,
  Inter,
  JetBrains_Mono,
  Lora,
  Manrope,
  Merriweather,
  Montserrat,
  Noto_Sans,
  Noto_Serif,
  Nunito_Sans,
  Outfit,
  Oxanium,
  Playfair_Display,
  Public_Sans,
  Raleway,
  Roboto,
  Roboto_Slab,
  Source_Sans_3,
  Space_Grotesk,
} from "next/font/google"
import type { PresetConfig } from "shadcn/preset"

// Every font a shadcn preset can pick, self-hosted by next/font as `--font-<id>`.
// themes.css maps data-font / data-font-heading to these variables. Only the default
// (Inter) and the code font (Geist Mono) are preloaded; the browser fetches another
// font's files the first time a page uses it. next/font needs each call assigned to its
// own module-level const with literal options, hence the repetition.

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  preload: true,
  variable: "--font-inter",
})
const notoSans = Noto_Sans({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-noto-sans",
})
const nunitoSans = Nunito_Sans({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-nunito-sans",
})
const figtree = Figtree({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-figtree",
})
const roboto = Roboto({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-roboto",
})
const raleway = Raleway({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-raleway",
})
const dmSans = DM_Sans({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-dm-sans",
})
const publicSans = Public_Sans({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-public-sans",
})
const outfit = Outfit({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-outfit",
})
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-jetbrains-mono",
})
const geist = Geist({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-geist",
})
const geistMono = Geist_Mono({
  subsets: ["latin"],
  display: "swap",
  preload: true,
  variable: "--font-geist-mono",
})
const lora = Lora({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-lora",
})
const merriweather = Merriweather({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-merriweather",
})
const playfairDisplay = Playfair_Display({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-playfair-display",
})
const notoSerif = Noto_Serif({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-noto-serif",
})
const robotoSlab = Roboto_Slab({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-roboto-slab",
})
const oxanium = Oxanium({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-oxanium",
})
const manrope = Manrope({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-manrope",
})
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-space-grotesk",
})
const montserrat = Montserrat({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-montserrat",
})
const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-ibm-plex-sans",
})
const sourceSans3 = Source_Sans_3({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-source-sans-3",
})
const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-instrument-sans",
})
const ebGaramond = EB_Garamond({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-eb-garamond",
})
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  weight: "400",
  variable: "--font-instrument-serif",
})

/** By preset font id. `satisfies` fails the build if shadcn adds a font. */
export const presetFonts = {
  inter,
  "noto-sans": notoSans,
  "nunito-sans": nunitoSans,
  figtree,
  roboto,
  raleway,
  "dm-sans": dmSans,
  "public-sans": publicSans,
  outfit,
  "jetbrains-mono": jetbrainsMono,
  geist,
  "geist-mono": geistMono,
  lora,
  merriweather,
  "playfair-display": playfairDisplay,
  "noto-serif": notoSerif,
  "roboto-slab": robotoSlab,
  oxanium,
  manrope,
  "space-grotesk": spaceGrotesk,
  montserrat,
  "ibm-plex-sans": ibmPlexSans,
  "source-sans-3": sourceSans3,
  "instrument-sans": instrumentSans,
  "eb-garamond": ebGaramond,
  "instrument-serif": instrumentSerif,
} satisfies Record<PresetConfig["font"], { variable: string }>

/** Class names that define every `--font-<id>` variable; put them on <html>. */
export const fontVariables = Object.values(presetFonts)
  .map((f) => f.variable)
  .join(" ")
