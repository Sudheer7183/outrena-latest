/**
 * PageTransition.tsx — subtle fade + slide-up page transition wrapper.
 *
 * Wraps routed page content (the <Outlet /> in AppLayout) so each navigation
 * animates in: opacity 0→1, y 8px→0, 0.2s ease-out. Uses framer-motion.
 */
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { useLocation } from "react-router-dom";

interface PageTransitionProps {
  children: ReactNode;
}

export function PageTransition({ children }: PageTransitionProps) {
  const location = useLocation();

  return (
    <motion.div
      key={location.pathname}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
