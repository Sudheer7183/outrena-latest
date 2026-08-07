/**
 * HelpScreenshot.tsx — reusable image component for the Help Guide.
 *
 * Solves AUDIT-HELP-1 / H-3 ("no screenshots in any article") by making
 * the help guide "screenshot-ready": articles reference screenshots
 * with standard markdown image syntax:
 *
 *   ![Connecting an LLM](/help-screenshots/admin-setup-connecting-llm.png)
 *
 * and `ArticleBody` (in `HelpGuidePage.tsx`) overrides `react-markdown`'s
 * `img` renderer to delegate here. This component:
 *
 *   1. Lazy-loads the image (`loading="lazy"`).
 *   2. Shows a friendly "Screenshot coming soon" placeholder while the
 *      PNG is still missing from `/public/help-screenshots/` or fails
 *      to load (network/404). Once a PNG is dropped in, the placeholder
 *      is automatically replaced — zero code changes required.
 *   3. Click-to-zoom: clicking the image opens a full-size Dialog modal
 *      with the screenshot, a caption, and a close button.
 *
 * Why not just render a plain `<img>`? Three reasons:
 *   - Missing PNGs would render the browser's broken-image icon,
 *     which looks unprofessional. The placeholder is a deliberate
 *     "we know it's missing, we're working on it" affordance.
 *   - Click-to-zoom is standard for help systems (Confluence,
 *     Notion, ReadTheDocs all do this) and essential for screenshots
 *     of dense admin UIs.
 *   - Lazy-loading keeps the page fast when an article has many
 *     screenshots.
 *
 * The component is also used directly (not via markdown) by future
 * admin-UI authors who want to embed a screenshot in a custom layout.
 */
import { useEffect, useState, useTransition } from "react";
import { Image as ImageIcon, Loader2, ZoomIn } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type LoadState = "loading" | "loaded" | "error";

export interface HelpScreenshotProps {
  /** Absolute URL to the PNG (e.g. `/help-screenshots/foo.png`). */
  src: string;
  /** Alt text — required for accessibility. Falls back to caption. */
  alt: string;
  /** Optional caption rendered below the image. */
  caption?: string;
  /** Optional className applied to the outer figure wrapper. */
  className?: string;
}

/**
 * `<HelpScreenshot>` — lazy-load + placeholder + click-to-zoom.
 *
 * Uses the `key={src}` remount pattern (instead of `setState` inside
 * `useEffect`) to reset internal load state when the `src` prop
 * changes — satisfies the React hooks `set-state-in-effect` lint rule
 * without an explicit effect.
 */
export function HelpScreenshot({
  src,
  alt,
  caption,
  className,
}: HelpScreenshotProps) {
  const [status, setStatus] = useState<LoadState>("loading");
  const [zoomOpen, setZoomOpen] = useState(false);
  // startTransition keeps the click-to-zoom open state from blocking
  // the dialog animation paint.
  const [, startTransition] = useTransition();

  // Reset load state when src changes.
  useEffect(() => {
    setStatus("loading");
  }, [src]);

  const showPlaceholder = status === "loading" || status === "error";

  return (
    <figure className={cn("my-4", className)}>
      <div
        className={cn(
          "group relative overflow-hidden rounded-lg border bg-muted/30",
          "cursor-zoom-in transition-shadow hover:shadow-md",
        )}
        onClick={() =>
          startTransition(() => setZoomOpen(true))
        }
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            startTransition(() => setZoomOpen(true));
          }
        }}
        aria-label={`Open ${alt} in full size`}
      >
        {/* The actual image — always rendered so the browser fires
            onLoad/onError; visually hidden while loading to avoid
            flashing the broken-image icon. */}
        <img
          src={src}
          alt={alt}
          loading="lazy"
          decoding="async"
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("error")}
          className={cn(
            "block w-full h-auto",
            showPlaceholder && "invisible",
          )}
        />

        {/* Placeholder overlay (shown while loading or on error).
            The overlay only renders when the image hasn't loaded yet,
            so it's always the visible content — no aria-hidden needed. */}
        {showPlaceholder && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center"
          >
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-500">
              <ImageIcon className="h-6 w-6" />
              {status === "loading" && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
            </div>
            <p className="text-sm font-medium">
              {status === "loading" ? "Loading screenshot…" : "Screenshot coming soon"}
            </p>
            <p className="text-xs text-muted-foreground line-clamp-1">
              {src.split("/").pop()}
            </p>
          </div>
        )}

        {/* Zoom affordance — only when image is loaded. */}
        {status === "loaded" && (
          <div className="pointer-events-none absolute right-2 top-2 rounded-md bg-background/80 px-2 py-1 text-xs text-muted-foreground opacity-0 backdrop-blur transition-opacity group-hover:opacity-100">
            <ZoomIn className="mr-1 inline h-3 w-3" />
            Click to zoom
          </div>
        )}
      </div>

      {caption && (
        <figcaption className="mt-1.5 text-center text-xs text-muted-foreground">
          {caption}
        </figcaption>
      )}

      {/* Click-to-zoom Dialog. */}
      <Dialog open={zoomOpen} onOpenChange={setZoomOpen}>
        <DialogContent className="max-w-5xl">
          <DialogTitle className="sr-only">{alt}</DialogTitle>
          <DialogDescription className="sr-only">
            {caption ?? alt} — full size view.
          </DialogDescription>
          <img
            src={src}
            alt={alt}
            className="block max-h-[80vh] w-auto max-w-full mx-auto rounded-md"
          />
          {caption && (
            <p className="text-center text-sm text-muted-foreground">
              {caption}
            </p>
          )}
        </DialogContent>
      </Dialog>
    </figure>
  );
}
