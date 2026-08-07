/**
 * slot.tsx — re-export of @radix-ui/react-slot for the `asChild` pattern
 * used by Button, DialogTrigger, SelectTrigger, etc.
 *
 * shadcn/ui convention: components that accept `asChild` spread their props
 * onto the single child element via Slot instead of rendering their own DOM
 * node.
 */
export { Slot } from "@radix-ui/react-slot";
