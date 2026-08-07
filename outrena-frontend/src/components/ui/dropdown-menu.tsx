/**
 * dropdown-menu.tsx — Radix DropdownMenu wrapper with shadcn/ui New York
 * styling.
 *
 * Exports the standard shadcn API: `DropdownMenu`, `DropdownMenuTrigger`,
 * `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuSeparator`,
 * `DropdownMenuLabel`, `DropdownMenuGroup`.
 *
 * Backwards-compat: the legacy OUTRENA `DropdownMenu` accepted a `trigger`
 * prop and rendered children directly. This component detects the legacy
 * `trigger` prop and auto-wraps in Radix Trigger + Content. New code can use
 * the standard shadcn pattern with explicit `DropdownMenuTrigger` +
 * `DropdownMenuContent`.
 *
 * `DropdownMenuItem` supports BOTH the legacy `onClick`/`destructive` props
 * and the shadcn `onSelect` prop.
 */
import * as React from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils";

const DropdownMenu = ({
  trigger,
  align = "end",
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Root> & {
  /** Legacy prop: if provided, auto-wraps in Trigger + Content. */
  trigger?: React.ReactNode;
  /** Legacy prop: alignment of the auto-generated content. */
  align?: "start" | "center" | "end";
}) => {
  // Legacy mode: `trigger` prop provided → auto-wrap.
  if (trigger !== undefined) {
    return (
      <DropdownMenuPrimitive.Root {...props}>
        <DropdownMenuPrimitive.Trigger asChild>
          {trigger}
        </DropdownMenuPrimitive.Trigger>
        <DropdownMenuContent align={align}>{children}</DropdownMenuContent>
      </DropdownMenuPrimitive.Root>
    );
  }

  // New shadcn pattern: caller provides Trigger + Content explicitly.
  return (
    <DropdownMenuPrimitive.Root {...props}>{children}</DropdownMenuPrimitive.Root>
  );
};
DropdownMenu.displayName = "DropdownMenu";

const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[12rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
        "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className,
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & {
    /** Legacy prop: adds red destructive styling. */
    destructive?: boolean;
    /** Legacy prop: maps to onSelect. */
    onClick?: () => void;
  }
>(({ className, destructive, onClick, onSelect, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    onSelect={(e) => {
      onClick?.();
      onSelect?.(e);
    }}
    className={cn(
      "relative flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      destructive && "text-red-600 focus:bg-red-50 focus:text-red-700 dark:focus:bg-red-950/40",
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName;

const DropdownMenuLabel = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Label>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Label
    ref={ref}
    className={cn("px-2 py-1.5 text-sm font-semibold", className)}
    {...props}
  />
));
DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName;

const DropdownMenuSeparator = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={cn("-mx-1 my-1 h-px bg-muted", className)}
    {...props}
  />
));
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName;

const DropdownMenuGroup = DropdownMenuPrimitive.Group;

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuGroup,
};
