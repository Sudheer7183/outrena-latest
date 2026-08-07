/**
 * tailwind.config.ts — Tailwind 4 (stable) compatibility config.
 *
 * Tailwind 4 is CSS-first by default. Design tokens (colors, radii) are
 * declared via `@theme inline` in `src/index.css` so the `bg-background`,
 * `text-foreground`, `border-border`, … utilities resolve correctly. This
 * JS config is retained for the `content` globs and as a compat surface.
 *
 * `darkMode` is configured in CSS via `@custom-variant dark (&:is(.dark *))`
 * (the TW4 native form), so it's omitted here. The `tailwindcss-animate`
 * plugin has been removed — `tw-animate-css` (imported in index.css) provides
 * the `animate-in`/`animate-out`/`fade-in-*` family used by shadcn/ui.
 */
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
  },
  plugins: [],
};

export default config;
