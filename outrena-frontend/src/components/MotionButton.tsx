/**
 * MotionButton.tsx — framer-motion-enhanced Button with subtle hover/tap
 * scale animations.
 *
 * Drop-in replacement for the shadcn Button that adds `whileHover` (scale
 * 1.02) and `whileTap` (scale 0.98). Uses the same cva variants as the base
 * Button so all `variant`/`size` props continue to work. Accepts an optional
 * `asChild` prop via Radix Slot for the `<Button asChild><Link/></Button>`
 * pattern (motion is skipped when `asChild` is set since the child element
 * would need its own motion wrapper).
 */
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-red-600 text-white hover:bg-red-600/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-muted text-muted-foreground hover:bg-muted/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface MotionButtonProps
  extends Omit<HTMLMotionProps<"button">, "ref">,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const MotionButton = forwardRef<HTMLButtonElement, MotionButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : motion.button;
    const motionProps = asChild
      ? {}
      : { whileHover: { scale: 1.02 }, whileTap: { scale: 0.98 } };
    return (
      // @ts-expect-error — Slot vs motion.button prop overlap is fine at runtime
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...motionProps}
        {...(props as ButtonHTMLAttributes<HTMLButtonElement>)}
      />
    );
  },
);
MotionButton.displayName = "MotionButton";
