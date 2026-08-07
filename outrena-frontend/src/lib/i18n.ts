/**
 * i18n.ts — locale extension point (URD FR-124).
 *
 * MVP ships en-US only, but all user-facing strings SHOULD be routed through
 * `t()` so additional locales can be added by dropping a catalog into
 * `CATALOGS` — no component changes required. The active locale is read from
 * localStorage ("outrena.locale") falling back to the browser language and
 * then en-US.
 */

type Catalog = Record<string, string>;

const enUS: Catalog = {
  // Keys are added lazily as strings are internationalised. `t()` falls back
  // to the key itself, so untranslated strings render unchanged.
};

const CATALOGS: Record<string, Catalog> = {
  "en-US": enUS,
  // "de-DE": deDE,  ← add new locales here (FR-124 extension point)
};

export function getLocale(): string {
  try {
    const stored = localStorage.getItem("outrena.locale");
    if (stored && CATALOGS[stored]) return stored;
  } catch {
    /* SSR / privacy mode */
  }
  const nav = typeof navigator !== "undefined" ? navigator.language : "en-US";
  return CATALOGS[nav] ? nav : "en-US";
}

export function setLocale(locale: string): void {
  if (!CATALOGS[locale]) throw new Error(`Unsupported locale: ${locale}`);
  localStorage.setItem("outrena.locale", locale);
}

export function t(key: string, params?: Record<string, string | number>): string {
  const catalog = CATALOGS[getLocale()] ?? enUS;
  let msg = catalog[key] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      msg = msg.replaceAll(`{${k}}`, String(v));
    }
  }
  return msg;
}

export const SUPPORTED_LOCALES = Object.keys(CATALOGS);
