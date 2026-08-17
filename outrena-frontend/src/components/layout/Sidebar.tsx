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
// import { NavLink } from "react-router-dom";
// import { NAV_SECTIONS } from "@/lib/nav-config";
// import { useAuth } from "@/context/AuthContext";
// import { ROLE_HIERARCHY } from "@/types/common";
// import { cn } from "@/lib/utils";
// import { ScrollArea } from "@/components/ui/scroll-area";
// import { OutrenaLockup } from "@/components/OutrenaLogo";
// import type { NavItem } from "@/lib/nav-config";

// /* ── Highlighted nav item ─────────────────────────────────────────────────── */
// /**
//  * Items with `highlight: true` get a violet-tinted background when inactive
//  * (matching the Next.js reference which used `highlight: true` + a gradient
//  * badge to draw attention to Autopilot Pipeline, Help Guide, and Prompt Mgmt).
//  *
//  * Active state still uses bg-primary/text-primary-foreground (same as every
//  * other item) so the active indicator is always consistent.
//  */
// function HighlightedNavLink({
//   item,
//   onNavigate,
// }: {
//   item: NavItem;
//   onNavigate?: () => void;
// }) {
//   const Icon = item.icon;
//   return (
//     <NavLink
//       to={item.path}
//       end={item.path === "/"}
//       onClick={onNavigate}
//       className={({ isActive }) =>
//         cn(
//           "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
//           isActive
//             ? "bg-primary text-primary-foreground"
//             : "bg-violet-50 text-violet-700 hover:bg-violet-100 hover:text-violet-800 dark:bg-violet-950/40 dark:text-violet-300 dark:hover:bg-violet-900/50 dark:hover:text-violet-200",
//         )
//       }
//     >
//       <Icon className="h-4 w-4 shrink-0" />
//       <span className="truncate">{item.label}</span>
//     </NavLink>
//   );
// }

// /* ── Standard nav item ────────────────────────────────────────────────────── */
// function StandardNavLink({
//   item,
//   onNavigate,
// }: {
//   item: NavItem;
//   onNavigate?: () => void;
// }) {
//   const Icon = item.icon;
//   return (
//     <NavLink
//       to={item.path}
//       end={item.path === "/"}
//       onClick={onNavigate}
//       className={({ isActive }) =>
//         cn(
//           "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
//           isActive
//             ? "bg-primary text-primary-foreground"
//             : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
//         )
//       }
//     >
//       <Icon className="h-4 w-4 shrink-0" />
//       <span className="truncate">{item.label}</span>
//     </NavLink>
//   );
// }

// /* ── Sidebar ─────────────────────────────────────────────────────────────── */
// export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
//   const { user } = useAuth();
//   const userLevel = user ? ROLE_HIERARCHY[user.role] : 0;

//   return (
//     <aside className="flex h-full w-64 flex-col border-r bg-card">
//       {/* Logo */}
//       <div className="flex h-16 items-center border-b px-5">
//         <OutrenaLockup width={120} />
//       </div>

//       {/* Nav sections */}
//       <ScrollArea maxHeightClass="flex-1" className="flex-1 px-3 py-4">
//         <nav className="space-y-6">
//           {NAV_SECTIONS.map((section) => {
//             const visible = section.items.filter(
//               (it) => ROLE_HIERARCHY[it.minimumRole] <= userLevel,
//             );
//             if (visible.length === 0) return null;

//             return (
//               <div key={section.id} className="space-y-1">
//                 {/* N-1: Section label — already rendered, preserved exactly */}
//                 <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
//                   {section.label}
//                 </p>

//                 {visible.map((item) =>
//                   item.highlight ? (
//                     // N-2/N-3/N-4: highlighted items get violet accent bg
//                     <HighlightedNavLink
//                       key={item.path}
//                       item={item}
//                       onNavigate={onNavigate}
//                     />
//                   ) : (
//                     <StandardNavLink
//                       key={item.path}
//                       item={item}
//                       onNavigate={onNavigate}
//                     />
//                   ),
//                 )}
//               </div>
//             );
//           })}
//         </nav>
//       </ScrollArea>

//       {/* Footer */}
//       <div className="border-t p-4 text-xs text-muted-foreground">
//         <p>v1.0 Alpha · AI-Powered Outreach OS</p>
//       </div>
//     </aside>
//   );
// }

/**
 * Sidebar.tsx — Collapsible section nav matching the Next.js reference UX.
 *
 * Each section header is a clickable toggle that shows/hides its items,
 * with a chevron and item count badge — exactly as in the Next.js screenshots.
 * Sections auto-expand when any child route is active.
 *
 * Changes:
 *   - Sections are now collapsible (click header to toggle)
 *   - Item count shown next to section label
 *   - Chevron rotates on open/close
 *   - Active child auto-expands its section on mount
 *   - highlighted items still get violet accent bg
 *   - defaultCollapsed from nav-config respected on first render
 */
// import { useState, useEffect } from "react";
// import { NavLink, useLocation } from "react-router-dom";
// import { ChevronDown } from "lucide-react";
// import { NAV_SECTIONS } from "@/lib/nav-config";
// import { useAuth } from "@/context/AuthContext";
// import { ROLE_HIERARCHY } from "@/types/common";
// import { cn } from "@/lib/utils";
// import { ScrollArea } from "@/components/ui/scroll-area";
// import { OutrenaLockup } from "@/components/OutrenaLogo";
// import type { NavItem, NavSection } from "@/lib/nav-config";

// /* ── Highlighted nav item ─────────────────────────────────────────────────── */
// function HighlightedNavLink({
//   item,
//   onNavigate,
// }: {
//   item: NavItem;
//   onNavigate?: () => void;
// }) {
//   const Icon = item.icon;
//   return (
//     <NavLink
//       to={item.path}
//       end={item.path === "/"}
//       onClick={onNavigate}
//       className={({ isActive }) =>
//         cn(
//           "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
//           isActive
//             ? "bg-primary text-primary-foreground"
//             : "bg-violet-50 text-violet-700 hover:bg-violet-100 hover:text-violet-800 dark:bg-violet-950/40 dark:text-violet-300 dark:hover:bg-violet-900/50 dark:hover:text-violet-200",
//         )
//       }
//     >
//       <Icon className="h-4 w-4 shrink-0" />
//       <span className="truncate">{item.label}</span>
//     </NavLink>
//   );
// }

// /* ── Standard nav item ────────────────────────────────────────────────────── */
// function StandardNavLink({
//   item,
//   onNavigate,
// }: {
//   item: NavItem;
//   onNavigate?: () => void;
// }) {
//   const Icon = item.icon;
//   return (
//     <NavLink
//       to={item.path}
//       end={item.path === "/"}
//       onClick={onNavigate}
//       className={({ isActive }) =>
//         cn(
//           "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
//           isActive
//             ? "bg-primary text-primary-foreground"
//             : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
//         )
//       }
//     >
//       <Icon className="h-4 w-4 shrink-0" />
//       <span className="truncate">{item.label}</span>
//     </NavLink>
//   );
// }

// /* ── Collapsible section ──────────────────────────────────────────────────── */
// function NavSectionBlock({
//   section,
//   visibleItems,
//   onNavigate,
// }: {
//   section: NavSection;
//   visibleItems: NavItem[];
//   onNavigate?: () => void;
// }) {
//   const location = useLocation();

//   // Auto-expand if any child is active
//   const hasActiveChild = visibleItems.some((item) =>
//     item.path === "/"
//       ? location.pathname === "/"
//       : location.pathname.startsWith(item.path),
//   );

//   const [open, setOpen] = useState(
//     hasActiveChild ? true : !(section.defaultCollapsed ?? false),
//   );

//   // Re-check when location changes (e.g. navigating via quick-action buttons)
//   useEffect(() => {
//     if (hasActiveChild) setOpen(true);
//   }, [hasActiveChild]);

//   // "Overview" section (top) is always visible without a toggle header
//   const isOverview = section.id === "top";

//   if (isOverview) {
//     return (
//       <div className="space-y-1">
//         {visibleItems.map((item) =>
//           item.highlight ? (
//             <HighlightedNavLink key={item.path} item={item} onNavigate={onNavigate} />
//           ) : (
//             <StandardNavLink key={item.path} item={item} onNavigate={onNavigate} />
//           ),
//         )}
//       </div>
//     );
//   }

//   return (
//     <div className="space-y-1">
//       {/* Section header — clickable toggle */}
//       <button
//         type="button"
//         onClick={() => setOpen((o) => !o)}
//         className={cn(
//           "flex w-full items-center justify-between rounded-md px-3 py-1.5",
//           "text-xs font-semibold uppercase tracking-wider",
//           "text-muted-foreground transition-colors hover:text-foreground",
//         )}
//       >
//         <span>{section.label}</span>
//         <div className="flex items-center gap-1.5">
//           {/* Item count badge — matches Next.js reference */}
//           <span
//             className={cn(
//               "rounded px-1.5 py-0.5 text-[10px] font-medium tabular-nums",
//               open
//                 ? "bg-muted text-muted-foreground"
//                 : "bg-muted/60 text-muted-foreground/70",
//             )}
//           >
//             {visibleItems.length}
//           </span>
//           <ChevronDown
//             className={cn(
//               "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
//               open ? "rotate-0" : "-rotate-90",
//             )}
//           />
//         </div>
//       </button>

//       {/* Items — animate open/close */}
//       {open && (
//         <div className="space-y-0.5 pl-0">
//           {visibleItems.map((item) =>
//             item.highlight ? (
//               <HighlightedNavLink key={item.path} item={item} onNavigate={onNavigate} />
//             ) : (
//               <StandardNavLink key={item.path} item={item} onNavigate={onNavigate} />
//             ),
//           )}
//         </div>
//       )}
//     </div>
//   );
// }

// /* ── Sidebar ─────────────────────────────────────────────────────────────── */
// export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
//   const { user } = useAuth();
//   const userLevel = user ? ROLE_HIERARCHY[user.role] : 0;

//   return (
//     <aside className="flex h-full w-64 flex-col border-r bg-card">
//       {/* Logo */}
//       <div className="flex h-16 items-center border-b px-5">
//         <OutrenaLockup width={120} />
//       </div>

//       {/* Nav sections */}
//       <ScrollArea maxHeightClass="flex-1" className="flex-1 px-3 py-4">
//         <nav className="space-y-2">
//           {NAV_SECTIONS.map((section) => {
//             const visible = section.items.filter(
//               (it) => ROLE_HIERARCHY[it.minimumRole] <= userLevel,
//             );
//             if (visible.length === 0) return null;

//             return (
//               <NavSectionBlock
//                 key={section.id}
//                 section={section}
//                 visibleItems={visible}
//                 onNavigate={onNavigate}
//               />
//             );
//           })}
//         </nav>
//       </ScrollArea>

//       {/* User footer */}
//       <div className="border-t p-3">
//         <div className="flex items-center gap-2 rounded-md px-2 py-1.5">
//           <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
//             {user?.name?.charAt(0)?.toUpperCase() ?? "U"}
//           </div>
//           <div className="min-w-0 flex-1">
//             <p className="truncate text-xs font-medium leading-tight">
//               {user?.name ?? "User"}
//             </p>
//             <p className="truncate text-[10px] leading-tight text-muted-foreground">
//               {user?.role ?? ""}
//             </p>
//           </div>
//         </div>
//         <p className="mt-2 px-2 text-[10px] text-muted-foreground">
//           v1.0 — AI Sales Co-pilot
//         </p>
//       </div>
//     </aside>
//   );
// }

import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { NAV_SECTIONS } from "@/lib/nav-config";
import { useAuth } from "@/context/AuthContext";
import { ROLE_HIERARCHY } from "@/types/common";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { OutrenaLockup } from "@/components/OutrenaLogo";
import type { NavItem, NavSection } from "@/lib/nav-config";
 
/* ── Highlighted nav item ─────────────────────────────────────────────────── */
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
 
/* ── Collapsible section ──────────────────────────────────────────────────── */
function NavSectionBlock({
  section,
  visibleItems,
  onNavigate,
}: {
  section: NavSection;
  visibleItems: NavItem[];
  onNavigate?: () => void;
}) {
  const location = useLocation();
 
  // Auto-expand if any child is active
  const hasActiveChild = visibleItems.some((item) =>
    item.path === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(item.path),
  );
 
  const [open, setOpen] = useState(
    hasActiveChild ? true : !(section.defaultCollapsed ?? false),
  );
 
  // Re-check when location changes (e.g. navigating via quick-action buttons)
  useEffect(() => {
    if (hasActiveChild) setOpen(true);
  }, [hasActiveChild]);
 
  // "Overview" section (top) is always visible without a toggle header
  const isOverview = section.id === "top";
 
  if (isOverview) {
    return (
      <div className="space-y-1">
        {visibleItems.map((item) =>
          item.highlight ? (
            <HighlightedNavLink key={item.path} item={item} onNavigate={onNavigate} />
          ) : (
            <StandardNavLink key={item.path} item={item} onNavigate={onNavigate} />
          ),
        )}
      </div>
    );
  }
 
  return (
    <div className="space-y-1">
      {/* Section header — clickable toggle */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex w-full items-center justify-between rounded-md px-3 py-1.5",
          "text-xs font-semibold uppercase tracking-wider",
          "text-muted-foreground transition-colors hover:text-foreground",
        )}
      >
        <span>{section.label}</span>
        <div className="flex items-center gap-1.5">
          {/* Item count badge — matches Next.js reference */}
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px] font-medium tabular-nums",
              open
                ? "bg-muted text-muted-foreground"
                : "bg-muted/60 text-muted-foreground/70",
            )}
          >
            {visibleItems.length}
          </span>
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
              open ? "rotate-0" : "-rotate-90",
            )}
          />
        </div>
      </button>
 
      {/* Items — animate open/close */}
      {open && (
        <div className="space-y-0.5 pl-0">
          {visibleItems.map((item) =>
            item.highlight ? (
              <HighlightedNavLink key={item.path} item={item} onNavigate={onNavigate} />
            ) : (
              <StandardNavLink key={item.path} item={item} onNavigate={onNavigate} />
            ),
          )}
        </div>
      )}
    </div>
  );
}
 
/* ── Sidebar ─────────────────────────────────────────────────────────────── */
export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const userLevel = user ? ROLE_HIERARCHY[user.role] : 0;
  const isSuperAdmin = user?.role === "SUPER_ADMIN";
 
  // SUPER_ADMIN only sees the Platform section — all other sections belong
  // to tenant schemas and are irrelevant (and inaccessible) to the platform admin.
  const sectionsToRender = isSuperAdmin
    ? NAV_SECTIONS.filter((s) => s.id === "platform")
    : NAV_SECTIONS;
 
  return (
    <aside className="flex h-full w-64 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center border-b px-5">
        <OutrenaLockup width={120} />
      </div>
 
      {/* Nav sections */}
      <ScrollArea maxHeightClass="flex-1" className="flex-1 px-3 py-4">
        <nav className="space-y-2">
          {sectionsToRender.map((section) => {
            const visible = section.items.filter(
              (it) => ROLE_HIERARCHY[it.minimumRole] <= userLevel,
            );
            if (visible.length === 0) return null;
 
            return (
              <NavSectionBlock
                key={section.id}
                section={section}
                visibleItems={visible}
                onNavigate={onNavigate}
              />
            );
          })}
        </nav>
      </ScrollArea>
 
      {/* User footer */}
      <div className="border-t p-3">
        <div className="flex items-center gap-2 rounded-md px-2 py-1.5">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            {user?.name?.charAt(0)?.toUpperCase() ?? "U"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium leading-tight">
              {user?.name ?? "User"}
            </p>
            <p className="truncate text-[10px] leading-tight text-muted-foreground">
              {user?.role ?? ""}
            </p>
          </div>
        </div>
        <p className="mt-2 px-2 text-[10px] text-muted-foreground">
          v1.0 — AI Sales Co-pilot
        </p>
      </div>
    </aside>
  );
}