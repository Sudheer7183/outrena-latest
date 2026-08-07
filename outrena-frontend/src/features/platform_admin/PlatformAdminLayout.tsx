/**
 * PlatformAdminLayout.tsx — separate console chrome for SUPER_ADMIN.
 *
 * NOT under <AppLayout>. Owns its own sidebar (Dashboard, Tenants, Signup
 * Approvals, Audit Logs, Platform Settings) and a topbar with a "Back to app"
 * link. Uses <Outlet /> for routed children.
 */
import { NavLink, Outlet, Link } from "react-router-dom";
import {
  ArrowLeft,
  Building2,
  Cpu,
  DollarSign,
  FileCheck2,
  Gauge,
  LayoutDashboard,
  PlugZap,
  ScrollText,
  Settings,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { ScrollArea } from "@/components/ui/scroll-area";

const NAV = [
  { label: "Dashboard", to: "/platform-admin", icon: LayoutDashboard, end: true },
  { label: "Tenants", to: "/platform-admin/tenants", icon: Building2 },
  { label: "Signup Approvals", to: "/platform-admin/approvals", icon: FileCheck2 },
  // SAAS2-FE: platform integrations + global LLM + usage + cost table
  { label: "Integrations", to: "/platform-admin/integrations", icon: PlugZap },
  { label: "Global LLM Config", to: "/platform-admin/llm-configs", icon: Cpu },
  { label: "Platform Usage", to: "/platform-admin/usage", icon: DollarSign },
  { label: "Cost Table", to: "/platform-admin/cost-table", icon: Gauge },
  { label: "Audit Logs", to: "/platform-admin/audit-logs", icon: ScrollText },
  { label: "Platform Settings", to: "/platform-admin/settings", icon: Settings },
];

export function PlatformAdminLayout() {
  const { user } = useAuth();
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r bg-card">
        <div className="flex h-16 items-center gap-2 border-b px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-bold tracking-tight">OUTRENA</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Platform Admin
            </span>
          </div>
        </div>
        <ScrollArea maxHeightClass="flex-1" className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </ScrollArea>
        <div className="border-t p-4">
          <Button asChild variant="outline" size="sm" className="w-full">
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
              Back to app
            </Link>
          </Button>
          <p className="mt-3 text-xs text-muted-foreground">
            Signed in as {user?.email}
          </p>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background px-6">
          <div>
            <p className="text-sm font-semibold">Platform Admin Console</p>
            <p className="text-xs text-muted-foreground">
              Cross-tenant operations · SUPER_ADMIN only
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldAlert className="h-4 w-4" />
            Elevated session
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
