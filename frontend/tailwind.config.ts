import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#F6F4EE",
        surface: "#FBFAF5",
        card: "#FFFFFF",
        line: "rgba(32,30,25,0.12)",
        lineStrong: "rgba(32,30,25,0.28)",
        accent: "#1D4ED8",
        accentDim: "rgba(29,78,216,0.10)",
        textPrimary: "#201E19",
        textSecondary: "#5C574D",
        textMuted: "#8A8478",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
        sans: ['"Instrument Sans"', "system-ui", "sans-serif"],
        serif: ['"Source Serif 4"', "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tight2: "-0.03em",
        tight3: "-0.05em",
      },
      borderRadius: {
        none: "0",
        sm: "2px",
        DEFAULT: "0",
      },
    },
  },
  plugins: [typography],
} satisfies Config;
