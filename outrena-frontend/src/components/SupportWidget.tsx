/**
 * SupportWidget.tsx — floating support button + quick-action popover.
 *
 * Mounted globally in <App /> for authenticated users. Renders a floating
 * button bottom-right after a 2s delay. Click opens a popover with quick
 * links: View my tickets, New ticket, Browse help guide.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  HelpCircle,
  LifeBuoy,
  MessageSquarePlus,
  Ticket,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function SupportWidget() {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);

  // Delay first appearance by 2s.
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 2_000);
    return () => clearTimeout(t);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.6 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-3"
        >
          <AnimatePresence>
            {open && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="w-72 rounded-lg border bg-popover p-2 text-popover-foreground shadow-lg"
              >
                <div className="px-3 py-2">
                  <p className="flex items-center gap-2 text-sm font-semibold">
                    <LifeBuoy className="h-4 w-4" />
                    How can we help?
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Pick a quick action or browse our docs.
                  </p>
                </div>
                <div className="space-y-1">
                  <QuickLink
                    to="/support"
                    icon={<Ticket className="h-4 w-4" />}
                    label="View my tickets"
                    onClick={() => setOpen(false)}
                  />
                  <QuickLink
                    to="/support?action=new"
                    icon={<MessageSquarePlus className="h-4 w-4" />}
                    label="Open a new ticket"
                    onClick={() => setOpen(false)}
                  />
                  <QuickLink
                    to="/help-guide"
                    icon={<HelpCircle className="h-4 w-4" />}
                    label="Browse help guide"
                    onClick={() => setOpen(false)}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                className="h-12 w-12 rounded-full shadow-lg"
                onClick={() => setOpen((v) => !v)}
                aria-label="Open support menu"
              >
                {open ? <X className="h-5 w-5" /> : <LifeBuoy className="h-5 w-5" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{open ? "Close support menu" : "Support & help"}</TooltipContent>
          </Tooltip>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function QuickLink({
  to,
  icon,
  label,
  onClick,
}: {
  to: string;
  icon: ReactNode;
  label: string;
  onClick?: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      <span className="text-muted-foreground">{icon}</span>
      <span>{label}</span>
    </Link>
  );
}
