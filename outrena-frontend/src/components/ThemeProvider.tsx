/**
 * ThemeProvider.tsx — next-themes provider for class-based dark mode.
 *
 * Wraps the app so any descendant can read/toggle the active theme via
 * `useTheme()` from next-themes. Configured for `attribute="class"` so the
 * `.dark` class is toggled on <html>, matching the shadcn/ui token system
 * in `src/index.css`.
 */
import type { ReactNode } from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: string;
}

export function ThemeProvider({
  children,
  defaultTheme = "system",
}: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme={defaultTheme}
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
