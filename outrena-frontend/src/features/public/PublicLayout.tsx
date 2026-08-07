/**
 * PublicLayout.tsx — shared chrome for unauthenticated marketing pages.
 *
 * Renders a sticky top-nav (Logo, Features, Pricing, About, Contact, Sign in,
 * Get started) and a 4-column footer (Product, Company, Legal, Contact).
 * `<Outlet />` is wrapped in a `<main>` with consistent vertical rhythm.
 *
 * Outside `<AppLayout>` — these routes are accessible without auth.
 */
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CookieConsentBanner } from "@/components/CookieConsentBanner";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { label: "Features", to: "/p#features" },
  { label: "Pricing", to: "/p/pricing" },
  { label: "About", to: "/p/about" },
  { label: "Contact", to: "/p/contact" },
];

export function PublicLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Top nav */}
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/p" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <span className="text-sm font-black">O</span>
            </div>
            <span className="text-lg font-bold tracking-tight">OUTRENA</span>
          </Link>

          <nav className="hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  cn(
                    "text-sm font-medium transition-colors hover:text-foreground",
                    isActive ? "text-foreground" : "text-muted-foreground",
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>

          <div className="hidden items-center gap-2 md:flex">
            <Button asChild variant="ghost" size="sm">
              <Link to="/login">Sign in</Link>
            </Button>
            <Button asChild size="sm">
              <Link to="/signup">Get started</Link>
            </Button>
          </div>

          <button
            type="button"
            className="md:hidden"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Toggle navigation"
          >
            {mobileOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </button>
        </div>

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="border-t bg-background px-4 py-4 md:hidden">
            <nav className="flex flex-col gap-3">
              {NAV_LINKS.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileOpen(false)}
                  className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  {link.label}
                </NavLink>
              ))}
              <div className="mt-2 flex flex-col gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link to="/login" onClick={() => setMobileOpen(false)}>
                    Sign in
                  </Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/signup" onClick={() => setMobileOpen(false)}>
                    Get started
                  </Link>
                </Button>
              </div>
            </nav>
          </div>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t bg-card">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-4 py-12 sm:px-6 lg:grid-cols-4 lg:px-8">
          <div className="col-span-2 lg:col-span-1">
            <Link to="/p" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <span className="text-sm font-black">O</span>
              </div>
              <span className="text-lg font-bold tracking-tight">OUTRENA</span>
            </Link>
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              The AI-powered outreach operating system for modern revenue
              teams.
            </p>
          </div>

          <div>
            <p className="text-sm font-semibold">Product</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link to="/p#features" className="text-muted-foreground hover:text-foreground">
                  Features
                </Link>
              </li>
              <li>
                <Link to="/p/pricing" className="text-muted-foreground hover:text-foreground">
                  Pricing
                </Link>
              </li>
              <li>
                <Link to="/signup" className="text-muted-foreground hover:text-foreground">
                  Start free trial
                </Link>
              </li>
              <li>
                <Link to="/login" className="text-muted-foreground hover:text-foreground">
                  Sign in
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-semibold">Company</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link to="/p/about" className="text-muted-foreground hover:text-foreground">
                  About
                </Link>
              </li>
              <li>
                <Link to="/p/contact" className="text-muted-foreground hover:text-foreground">
                  Contact
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-semibold">Legal</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link to="/p/privacy" className="text-muted-foreground hover:text-foreground">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link to="/p/terms" className="text-muted-foreground hover:text-foreground">
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link to="/p/dpa" className="text-muted-foreground hover:text-foreground">
                  Data Processing Agreement
                </Link>
              </li>
              <li>
                <Link to="/p/gdpr-rights" className="text-muted-foreground hover:text-foreground">
                  GDPR Rights · DSR
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t py-6 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} OUTRENA · AI-Powered Outreach Operating
          System
        </div>
      </footer>

      {/* SAAS2-FE: cookie consent banner — public pages only */}
      <CookieConsentBanner />
    </div>
  );
}
