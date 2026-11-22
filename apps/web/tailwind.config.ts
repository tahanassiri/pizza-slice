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
        sans: ["var(--font-vazirmatn)", "Vazirmatn", "Tahoma", "sans-serif"],
        display: ["var(--font-syne)", "var(--font-vazirmatn)", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
