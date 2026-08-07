/**
 * dialog.tsx — Radix Dialog wrapper with shadcn/ui New York styling.
 *
 * Exports the standard shadcn API: `Dialog`, `DialogTrigger`, `DialogOverlay`,
 * `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`,
 * `DialogDescription`, `DialogClose`.
 *
 * Backwards-compat: the legacy OUTRENA call sites render children directly
 * inside `<Dialog open onOpenChange>` without a `<DialogContent>` wrapper.
 * The `Dialog` component detects this (no `DialogContent` among children)
 * and auto-wraps in Portal + Overlay + Content so legacy code keeps working.
 * New code can use the standard shadcn pattern explicitly.
 */
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = ({
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Root>) => {
  // Detect whether children already include a DialogContent (new shadcn
  // pattern). If so, render as a pure Radix Root. Otherwise auto-wrap in
  // Portal + Overlay + Content for the legacy call sites.
  const hasExplicitContent = React.Children.toArray(children).some(
    (child) => React.isValidElement(child) && child.type === DialogContent,
  );

  if (hasExplicitContent) {
    return <DialogPrimitive.Root {...props}>{children}</DialogPrimitive.Root>;
  }

  return (
    <DialogPrimitive.Root {...props}>
      <DialogPrimitive.Portal>
        <DialogOverlay />
        <DialogContent>{children}</DialogContent>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};
Dialog.displayName = "Dialog";

const DialogTrigger = DialogPrimitive.Trigger;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Content
    ref={ref}
    className={cn(
      "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg",
      className,
    )}
    {...props}
  >
    {children}
    <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none">
      <X className="h-4 w-4" />
      <span className="sr-only">Close</span>
    </DialogPrimitive.Close>
  </DialogPrimitive.Content>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}
      {...props}
    />
  );
}
DialogHeader.displayName = "DialogHeader";

function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
        className,
      )}
      {...props}
    />
  );
}
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

/**
 * DialogClose — supports BOTH the shadcn `asChild` pattern and the legacy
 * OUTRENA `onClose` callback. When `onClose` is provided (legacy), the
 * component renders nothing because DialogContent already includes a
 * built-in close X and `onOpenChange(false)` handles state. When `asChild`
 * is set, it renders as a Radix Close Slot wrapping the child (shadcn).
 */
const DialogClose = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Close>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Close> & {
    onClose?: () => void;
  }
>(({ onClose, asChild, children, ...props }, ref) => {
  // Legacy mode: `onClose` provided → no-op render (DialogContent's built-in
  // X + the Dialog's onOpenChange handle closing).
  if (onClose && !asChild) return null;

  return (
    <DialogPrimitive.Close ref={ref} asChild={asChild} {...props}>
      {children}
    </DialogPrimitive.Close>
  );
});
DialogClose.displayName = "DialogClose";

export {
  Dialog,
  DialogTrigger,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogClose,
};
