/**
 * info-label.tsx — form field Label with an info-icon Tooltip.
 *
 * For technical fields whose meaning isn't obvious from the label text alone,
 * wrap the label with <InfoLabel label="Seniority Tier" info="C_Suite = C-level, Director = VP/Director, IC = Individual Contributor" />.
 * Renders a standard shadcn <Label> followed by a small <HelpCircle> icon
 * wrapped in a shadcn <Tooltip>.
 */
import * as React from "react";
import { HelpCircle } from "lucide-react";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface InfoLabelProps
  extends React.ComponentPropsWithoutRef<typeof Label> {
  /** The visible label text. */
  label: string;
  /** The tooltip content shown on hover/focus of the info icon. */
  info: string;
  /** Optional `htmlFor` to associate with the input. */
  htmlFor?: string;
}

export const InfoLabel = React.forwardRef<HTMLLabelElement, InfoLabelProps>(
  ({ label, info, htmlFor, className, children, ...props }, ref) => (
    <div className="flex items-center gap-1.5">
      <Label ref={ref} htmlFor={htmlFor} className={cn(className)} {...props}>
        {label}
      </Label>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={`About ${label}`}
            className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{info}</TooltipContent>
      </Tooltip>
      {children}
    </div>
  ),
);
InfoLabel.displayName = "InfoLabel";
