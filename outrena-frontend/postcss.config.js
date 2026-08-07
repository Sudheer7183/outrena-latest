/**
 * PostCSS config — Tailwind 4 stable.
 *
 * Tailwind 4 ships its own PostCSS plugin (`@tailwindcss/postcss`) which
 * replaces the v3 `tailwindcss` + `autoprefixer` pair. Autoprefixer is kept
 * for any third-party CSS that still needs vendor prefixing.
 */
export default {
  plugins: {
    "@tailwindcss/postcss": {},
    autoprefixer: {},
  },
};
