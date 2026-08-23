/**
 * PlatformAdminLayout.tsx — Shell for all /platform-admin/* pages.
 *
 * Provides a top navigation bar with links to each platform admin section
 * and renders <Outlet /> for the active child route.
 */
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import {
  BarChart2,
  Building2,
  FileText,
  Globe,
  LayoutDashboard,
  LogOut,
  Settings,
  UserCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { to: "/platform-admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/platform-admin/tenants", label: "Tenants", icon: Building2 },
  { to: "/platform-admin/signups", label: "Signups", icon: UserCheck },
  { to: "/platform-admin/audit-logs", label: "Audit Logs", icon: FileText },
  { to: "/platform-admin/integrations", label: "Integrations", icon: Globe },
  { to: "/platform-admin/usage", label: "Usage", icon: BarChart2 },
  { to: "/platform-admin/settings", label: "Settings", icon: Settings },
];

export function PlatformAdminLayout() {
  const { logout, user } = useAuth();

  return (
    <div className="flex min-h-screen flex-col bg-muted/30">
      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b bg-background shadow-sm">
        <div className="mx-auto flex max-w-screen-xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold tracking-tight text-primary">
              OUTRENA
            </span>
            <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-semibold uppercase text-primary">
              Platform Admin
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-muted-foreground sm:block">
              {user?.email}
            </span>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="mr-1.5 h-4 w-4" />
              Sign out
            </Button>
          </div>
        </div>

        {/* Nav tabs */}
        <nav className="mx-auto max-w-screen-xl overflow-x-auto px-4">
          <ul className="flex gap-1 pb-0">
            {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                      isActive
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      {/* Page content */}
      <main className="mx-auto w-full max-w-screen-xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
