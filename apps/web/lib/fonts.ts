import localFont from "next/font/local";

/**
 * Dastkhat FaNum — primary UI (Persian + Latin; digits as ۰–۹).
 * All 9 static weights + variable range so Tailwind font-* maps cleanly.
 */
export const dastkhat = localFont({
  src: [
    { path: "../fonts/dastkhat/DastkhatFaNum-Thin.woff2", weight: "100", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-ExtraLight.woff2", weight: "200", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-Light.woff2", weight: "300", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-Medium.woff2", weight: "500", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-Bold.woff2", weight: "700", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-ExtraBold.woff2", weight: "800", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatFaNum-Black.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-dastkhat",
  display: "swap",
  preload: true,
  adjustFontFallback: false,
});

/** Dastkhat Mono — run IDs, HS codes, URLs (Latin tabular). */
export const dastkhatMono = localFont({
  src: [
    { path: "../fonts/dastkhat/DastkhatMono-Thin.woff2", weight: "100", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-ExtraLight.woff2", weight: "200", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-Light.woff2", weight: "300", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-Medium.woff2", weight: "500", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-Bold.woff2", weight: "700", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-ExtraBold.woff2", weight: "800", style: "normal" },
    { path: "../fonts/dastkhat/DastkhatMono-Black.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-dastkhat-mono",
  display: "swap",
  preload: false,
  adjustFontFallback: false,
});
