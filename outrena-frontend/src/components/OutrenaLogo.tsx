/**
 * OutrenaLogo.tsx — brand logo component.
 *
 * Renders the Outrena lockup (light or dark variant) depending on the current
 * theme, or the app icon when only a square mark is needed.
 *
 * Uses base64-embedded assets so the logo renders without any network
 * request — safe in every deployment environment.
 */
import { useTheme } from "next-themes";
import { LOGO_LIGHT, LOGO_DARK, APP_ICON } from "@/lib/brand-assets";

interface LogoProps {
  /** Width in px (height is auto-calculated from aspect ratio 2000:384 ≈ 5.2:1) */
  width?: number;
  className?: string;
}

interface IconProps {
  size?: number;
  className?: string;
}

/**
 * Full horizontal lockup — "OUTRENA" wordmark + icon.
 * Switches automatically between light and dark variants.
 */
export function OutrenaLockup({ width = 140, className }: LogoProps) {
  const { resolvedTheme } = useTheme();
  const src = resolvedTheme === "dark" ? LOGO_DARK : LOGO_LIGHT;
  const height = Math.round(width * (384 / 2000));
  return (
    <img
      src={src}
      alt="Outrena"
      width={width}
      height={height}
      className={className}
      draggable={false}
    />
  );
}

/**
 * Square app icon — use where a compact square mark is needed (favicon, avatar).
 */
export function OutrenaIcon({ size = 32, className }: IconProps) {
  return (
    <img
      src={APP_ICON}
      alt="Outrena"
      width={size}
      height={size}
      className={className}
      draggable={false}
    />
  );
}
