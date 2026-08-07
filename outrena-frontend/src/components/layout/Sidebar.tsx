// /**
//  * Sidebar.tsx — 7-section nav with role-based filtering (migration §7.3).
//  *
//  * Renders `NAV_SECTIONS`, hiding any section whose items are all above the
//  * current user's role, and any individual item the user can't access.
//  *
//  * PROD-1: Replaced the placeholder "O" text mark with the real Outrena
//  * lockup via <OutrenaLockup>. Version footer updated to v1.0 alpha.
//  */
// import { NavLink } from "react-router-dom";
// import { NAV_SECTIONS } from "@/lib/nav-config";
// import { useAuth } from "@/context/AuthContext";
// import { ROLE_HIERARCHY } from "@/types/common";
// import { cn } from "@/lib/utils";
// import { ScrollArea } from "@/components/ui/scroll-area";
// import { OutrenaLockup } from "@/components/OutrenaLogo";

// export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
//   const { user } = useAuth();
//   const userLevel = user ? ROLE_HIERARCHY[user.role] : 0;

//   return (
//     <aside className="flex h-full w-64 flex-col border-r bg-card">
//       <div className="flex h-16 items-center border-b px-5">
//         <OutrenaLockup width={120} />
//       </div>
//       <ScrollArea maxHeightClass="flex-1" className="flex-1 px-3 py-4">
//         <nav className="space-y-6">
//           {NAV_SECTIONS.map((section) => {
//             const visible = section.items.filter(
//               (it) => ROLE_HIERARCHY[it.minimumRole] <= userLevel,
//             );
//             if (visible.length === 0) return null;
//             return (
//               <div key={section.id} className="space-y-1">
//                 <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
//                   {section.label}
//                 </p>
//                 {visible.map((item) => (
//                   <NavLink
//                     key={item.path}
//                     to={item.path}
//                     end={item.path === "/"}
//                     onClick={onNavigate}
//                     className={({ isActive }) =>
//                       cn(
//                         "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
//                         isActive
//                           ? "bg-primary text-primary-foreground"
//                           : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
//                       )
//                     }
//                   >
//                     <item.icon className="h-4 w-4 shrink-0" />
//                     <span className="truncate">{item.label}</span>
//                   </NavLink>
//                 ))}
//               </div>
//             );
//           })}
//         </nav>
//       </ScrollArea>
//       <div className="border-t p-4 text-xs text-muted-foreground">
//         <p>v1.0 Alpha · AI-Powered Outreach OS</p>
//       </div>
//     </aside>
//   );
// }

/**
 * Sidebar.tsx — 7-section nav with role-based filtering (migration §7.3).
 *
 * Renders `NAV_SECTIONS`, hiding any section whose items are all above the
 * current user's role, and any individual item the user can't access.
 *
 * Gap fixes applied (N-1 through N-4):
 *   N-1  Section labels already rendered — preserved.
 *   N-2  Autopilot Pipeline (highlight:true) gets violet gradient bg + Rocket icon.
 *   N-3  Help Guide (highlight:true) gets the same accent treatment.
 *   N-4  Prompt Management (highlight:true) gets the same accent treatment.
 *
 * PROD-1: Real Outrena lockup via <OutrenaLockup>. Version footer v1.0 alpha.
 */
import { NavLink } from "react-router-dom";
import { NAV_SECTIONS } from "@/lib/nav-config";
import { useAuth } from "@/context/AuthContext";
import { ROLE_HIERARCHY } from "@/types/common";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { OutrenaLockup } from "@/components/OutrenaLogo";
import type { NavItem } from "@/lib/nav-config";

/* ── Highlighted nav item ─────────────────────────────────────────────────── */
/**
 * Items with `highlight: true` get a violet-tinted background when inactive
 * (matching the Next.js reference which used `highlight: true` + a gradient
 * badge to draw attention to Autopilot Pipeline, Help Guide, and Prompt Mgmt).
 *
 * Active state still uses bg-primary/text-primary-foreground (same as every
 * other item) so the active indicator is always consistent.
 */
function HighlightedNavLink({
  item,
  onNavigate,
}: {
  item: NavItem;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary text-primary-foreground"
            : "bg-violet-50 text-violet-700 hover:bg-violet-100 hover:text-violet-800 dark:bg-violet-950/40 dark:text-violet-300 dark:hover:bg-violet-900/50 dark:hover:text-violet-200",
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{item.label}</span>
    </NavLink>
  );
}

/* ── Standard nav item ────────────────────────────────────────────────────── */
function StandardNavLink({
  item,
  onNavigate,
}: {
  item: NavItem;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{item.label}</span>
    </NavLink>
  );
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const userLevel = user ? ROLE_HIERARCHY[user.role] : 0;

  return (
    <aside className="flex h-full w-64 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center border-b px-5">
        <OutrenaLockup width={120} />
      </div>

      {/* Nav sections */}
      <ScrollArea maxHeightClass="flex-1" className="flex-1 px-3 py-4">
        <nav className="space-y-6">
          {NAV_SECTIONS.map((section) => {
            const visible = section.items.filter(
              (it) => ROLE_HIERARCHY[it.minimumRole] <= userLevel,
            );
            if (visible.length === 0) return null;

            return (
              <div key={section.id} className="space-y-1">
                {/* N-1: Section label — already rendered, preserved exactly */}
                <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {section.label}
                </p>

                {visible.map((item) =>
                  item.highlight ? (
                    // N-2/N-3/N-4: highlighted items get violet accent bg
                    <HighlightedNavLink
                      key={item.path}
                      item={item}
                      onNavigate={onNavigate}
                    />
                  ) : (
                    <StandardNavLink
                      key={item.path}
                      item={item}
                      onNavigate={onNavigate}
                    />
                  ),
                )}
              </div>
            );
          })}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t p-4 text-xs text-muted-foreground">
        <p>v1.0 Alpha · AI-Powered Outreach OS</p>
      </div>
    </aside>
  );
}