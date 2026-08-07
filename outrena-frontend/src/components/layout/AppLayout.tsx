/**
 * AppLayout.tsx — sidebar + topbar shell with <Outlet /> for routed pages.
 *
 * Responsive: sidebar is fixed on md+, and a slide-over drawer on mobile
 * (toggled from the topbar menu button). The footer is sticky to the bottom
 * per the UI rules (min-h-screen flex-col, footer mt-auto).
 */
import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { PageTransition } from "@/components/PageTransition";
import { OnboardingChecklist } from "@/components/OnboardingChecklist";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <div className="flex flex-1">
        {/* Desktop sidebar */}
        <div className="hidden md:flex">
          <Sidebar />
        </div>
        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <div
              className="absolute inset-0 bg-black/50"
              onClick={() => setMobileOpen(false)}
              aria-hidden
            />
            <div className={cn("absolute left-0 top-0 h-full")}>
              <Sidebar onNavigate={() => setMobileOpen(false)} />
            </div>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onMenuClick={() => setMobileOpen(true)} />
          <main className="flex-1 p-4 sm:p-6">
            <PageTransition>
              <Outlet />
            </PageTransition>
          </main>
          <footer className="mt-auto border-t bg-card px-6 py-4 text-center text-xs text-muted-foreground">
            OUTRENA — AI-Powered Outreach Operating System · © {new Date().getFullYear()}
          </footer>
        </div>
      </div>
      {/* Post-login onboarding checklist modal (FR-E1-007) */}
      <OnboardingChecklist />
    </div>
  );
}
