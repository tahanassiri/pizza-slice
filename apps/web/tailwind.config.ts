import type { Config } from "tailwindcss";

export default {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./features/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        "ink-muted": "var(--ink-muted)",
        paper: "var(--paper)",
        fog: "var(--fog)",
        line: "var(--line)",
        accent: "var(--accent)",
        mock: "var(--mock)",
      },
      fontFamily: {
        sans: [
          "var(--font-dastkhat)",
          "Dastkhat FaNum",
          "Tahoma",
          "sans-serif",
        ],
        display: [
          "var(--font-dastkhat)",
          "Dastkhat FaNum",
          "Tahoma",
          "sans-serif",
        ],
        mono: [
          "var(--font-dastkhat-mono)",
          "Dastkhat Mono",
          "ui-monospace",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      fontWeight: {
        thin: "100",
        extralight: "200",
        light: "300",
        normal: "400",
        medium: "500",
        semibold: "600",
        bold: "700",
        extrabold: "800",
        black: "900",
      },
    },
  },
  plugins: [],
} satisfies Config;
