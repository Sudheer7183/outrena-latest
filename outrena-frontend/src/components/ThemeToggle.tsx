/**
 * ThemeToggle.tsx — light/dark/system theme switcher.
 *
 * Uses `useTheme()` from next-themes. Renders a ghost Button with a Sun icon
 * in dark mode and a Moon icon in light mode. Mounted-ready (guards against
 * SSR/hydration mismatch by waiting for `mounted` to flip true).
 */
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // next-themes reads from localStorage / system — avoid hydration mismatch
  // by only rendering the icon after mount on the client.
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          onClick={() => setTheme(isDark ? "light" : "dark")}
        >
          {mounted ? (
            isDark ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )
          ) : (
            // placeholder with same dimensions to prevent layout shift
            <Sun className="h-5 w-5 opacity-0" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{isDark ? "Switch to light mode" : "Switch to dark mode"}</TooltipContent>
    </Tooltip>
  );
}
