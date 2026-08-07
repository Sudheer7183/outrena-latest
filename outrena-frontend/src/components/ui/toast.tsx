/**
 * toast.tsx — Radix Toast wrapper + useToast hook + Toaster (shadcn pattern).
 *
 * Note: OUTRENA's primary toast system is `sonner` (wired in App.tsx via
 * `<Toaster richColors />`). This Radix Toast wrapper is provided for
 * completeness so the @radix-ui/react-toast dependency is exercised and any
 * component that prefers the imperative `useToast()` API can use it.
 *
 * Usage:
 *   const { toast } = useToast();
 *   toast({ title: "Saved", description: "Changes persisted." });
 *   <Toaster />   // mount once near the app root
 */
import * as React from "react";
import * as ToastPrimitives from "@radix-ui/react-toast";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const ToastProvider = ToastPrimitives.Provider;

const ToastViewport = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Viewport>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Viewport
    ref={ref}
    className={cn(
      "fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]",
      className,
    )}
    {...props}
  />
));
ToastViewport.displayName = ToastPrimitives.Viewport.displayName;

const toastVariants = cva(
  "group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border p-4 pr-8 shadow-lg transition-all data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full",
  {
    variants: {
      variant: {
        default: "border bg-background text-foreground",
        destructive:
          "destructive group border-destructive bg-destructive text-destructive-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

const Toast = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Root> &
    VariantProps<typeof toastVariants>
>(({ className, variant, ...props }, ref) => (
  <ToastPrimitives.Root
    ref={ref}
    className={cn(toastVariants({ variant }), className)}
    {...props}
  />
));
Toast.displayName = ToastPrimitives.Root.displayName;

const ToastAction = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Action>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Action>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Action
    ref={ref}
    className={cn(
      "inline-flex h-8 shrink-0 items-center justify-center rounded-md border bg-transparent px-3 text-sm font-medium ring-offset-background transition-colors hover:bg-secondary focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
ToastAction.displayName = ToastPrimitives.Action.displayName;

const ToastClose = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Close>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Close>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Close
    ref={ref}
    className={cn(
      "absolute right-2 top-2 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity hover:text-foreground focus:opacity-100 focus:outline-none focus:ring-2 group-hover:opacity-100",
      className,
    )}
    toast-close=""
    {...props}
  >
    <X className="h-4 w-4" />
  </ToastPrimitives.Close>
));
ToastClose.displayName = ToastPrimitives.Close.displayName;

const ToastTitle = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Title>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Title>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Title
    ref={ref}
    className={cn("text-sm font-semibold", className)}
    {...props}
  />
));
ToastTitle.displayName = ToastPrimitives.Title.displayName;

const ToastDescription = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Description>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Description>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Description
    ref={ref}
    className={cn("text-sm opacity-90", className)}
    {...props}
  />
));
ToastDescription.displayName = ToastPrimitives.Description.displayName;

type ToastProps = React.ComponentPropsWithoutRef<typeof Toast>;
type ToastActionElement = React.ReactElement<typeof ToastAction>;

// ── useToast hook (shadcn pattern) ────────────────────────────────────────

const TOAST_LIMIT = 3;
const TOAST_REMOVE_DELAY = 5_000;

type ToasterToast = ToastProps & {
  id: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: ToastActionElement;
};

let count = 0;
function genId() {
  count = (count + 1) % Number.MAX_SAFE_INTEGER;
  return count.toString();
}

type State = { toasts: ToasterToast[] };

const listeners: Array<(state: State) => void> = [];
let memoryState: State = { toasts: [] };

function reducer(state: State, action: {
  type: "ADD" | "UPDATE" | "DISMISS" | "REMOVE";
  toast?: Partial<ToasterToast>;
  toasts?: ToasterToast[];
  toastId?: string;
}): State {
  switch (action.type) {
    case "ADD":
      return {
        toasts: [action.toast as ToasterToast, ...state.toasts].slice(
          0,
          TOAST_LIMIT,
        ),
      };
    case "UPDATE":
      return {
        toasts: state.toasts.map((t) =>
          t.id === action.toast?.id ? { ...t, ...action.toast } : t,
        ),
      };
    case "DISMISS": {
      const { toastId } = action;
      if (toastId === undefined) {
        return { toasts: state.toasts.map((t) => ({ ...t, open: false })) };
      }
      if (toastId) addToRemoveQueue(toastId);
      return {
        toasts: state.toasts.map((t) =>
          t.id === toastId ? { ...t, open: false } : t,
        ),
      };
    }
    case "REMOVE": {
      const { toastId } = action;
      if (toastId === undefined) return { toasts: [] };
      return { toasts: state.toasts.filter((t) => t.id !== toastId) };
    }
    default:
      return state;
  }
}

const timeouts = new Map<string, ReturnType<typeof setTimeout>>();

function addToRemoveQueue(toastId: string) {
  if (timeouts.has(toastId)) return;
  const timeout = setTimeout(() => {
    timeouts.delete(toastId);
    dispatch({ type: "REMOVE", toastId });
  }, TOAST_REMOVE_DELAY);
  timeouts.set(toastId, timeout);
}

function dispatch(action: Parameters<typeof reducer>[1]) {
  memoryState = reducer(memoryState, action);
  listeners.forEach((l) => l(memoryState));
}

type ToastOptions = Omit<ToasterToast, "id">;

function toast({ ...props }: ToastOptions) {
  const id = genId();
  const update = (t: ToasterToast) =>
    dispatch({ type: "UPDATE", toast: { ...t, id } });
  const dismiss = () => dispatch({ type: "DISMISS", toastId: id });

  dispatch({
    type: "ADD",
    toast: {
      ...props,
      id,
      open: true,
      onOpenChange: (open) => {
        if (!open) dismiss();
      },
    },
  });

  return { id, dismiss, update };
}

function useToast() {
  const [state, setState] = React.useState<State>(memoryState);
  React.useEffect(() => {
    listeners.push(setState);
    return () => {
      const idx = listeners.indexOf(setState);
      if (idx > -1) listeners.splice(idx, 1);
    };
  }, [state]);
  return {
    ...state,
    toast,
    dismiss: (toastId?: string) => dispatch({ type: "DISMISS", toastId }),
  };
}

// ── Toaster component (mount near app root) ───────────────────────────────

function Toaster() {
  const { toasts } = useToast();
  return (
    <ToastProvider>
      {toasts.map(({ id, title, description, action, ...props }) => (
        <Toast key={id} {...props}>
          <div className="grid gap-1">
            {title && <ToastTitle>{title}</ToastTitle>}
            {description && <ToastDescription>{description}</ToastDescription>}
          </div>
          {action}
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}

export {
  type ToastProps,
  type ToastActionElement,
  ToastProvider,
  ToastViewport,
  Toast,
  ToastAction,
  ToastClose,
  ToastTitle,
  ToastDescription,
  Toaster,
  useToast,
};
