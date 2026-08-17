// /**
//  * Topbar.tsx — sticky top bar with mobile menu toggle, theme switcher, and
//  * user menu.
//  */
// import { Bell, HelpCircle, LogOut, Menu } from "lucide-react";
// import { Link } from "react-router-dom";
// import { useQuery } from "@tanstack/react-query";
// import { useAuth } from "@/context/AuthContext";
// import { http } from "@/services/apiClient";
// import { Button } from "@/components/ui/button";
// import {
//   DropdownMenu,
//   DropdownMenuItem,
//   DropdownMenuLabel,
//   DropdownMenuSeparator,
//   DropdownMenuTrigger,
//   DropdownMenuContent,
// } from "@/components/ui/dropdown-menu";
// import {
//   Tooltip,
//   TooltipContent,
//   TooltipTrigger,
// } from "@/components/ui/tooltip";
// import { ThemeToggle } from "@/components/ThemeToggle";
// import { initials } from "@/lib/utils";
// import { Badge } from "@/components/ui/badge";

// export function Topbar({ onMenuClick }: { onMenuClick?: () => void }) {
//   const { user, logout, isAuthenticated } = useAuth();

//   // Notification bell — Help Guide §Compliance: "notification bell widget"
//   const { data: notifData } = useQuery({
//     queryKey: ["notifications", "unread-count"],
//     queryFn: () => http.get<{ unread_count: number }>("/api/v1/notifications/unread-count").catch(() => ({ unread_count: 0 })),
//     enabled: isAuthenticated,
//     staleTime: 30_000,
//   });
//   const unreadCount = notifData?.unread_count ?? 0;

//   return (
//     <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background px-4 sm:px-6">
//       <div className="flex items-center gap-3">
//         <Tooltip>
//           <TooltipTrigger asChild>
//             <Button
//               variant="ghost"
//               size="icon"
//               className="md:hidden"
//               onClick={onMenuClick}
//               aria-label="Toggle navigation"
//             >
//               <Menu className="h-5 w-5" />
//             </Button>
//           </TooltipTrigger>
//           <TooltipContent>Toggle navigation</TooltipContent>
//         </Tooltip>
//         <div className="hidden sm:block">
//           <p className="text-sm font-medium">Welcome back, {user?.name ?? "User"}</p>
//           <p className="text-xs text-muted-foreground">
//             {user?.email}
//             {user?.tenantSlug ? ` · ${user.tenantSlug}` : " · platform"}
//           </p>
//         </div>
//       </div>
//       <div className="flex items-center gap-3">
//         {user && (
//           <Badge variant="secondary" className="hidden sm:inline-flex">
//             {user.role.replace("_", " ")}
//           </Badge>
//         )}
//         <Tooltip>
//           <TooltipTrigger asChild>
//             <Button variant="ghost" size="icon" aria-label="Help guide" asChild>
//               <Link to="/help-guide">
//                 <HelpCircle className="h-5 w-5" />
//               </Link>
//             </Button>
//           </TooltipTrigger>
//           <TooltipContent>Help Guide — docs &amp; walkthroughs</TooltipContent>
//         </Tooltip>
//         {/* Notification bell — Help Guide §Compliance */}
//         <Tooltip>
//           <TooltipTrigger asChild>
//             <Button variant="ghost" size="icon" aria-label="Notifications" asChild>
//               <Link to="/notifications" className="relative">
//                 <Bell className="h-5 w-5" />
//                 {unreadCount > 0 && (
//                   <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
//                     {unreadCount > 9 ? "9+" : unreadCount}
//                   </span>
//                 )}
//               </Link>
//             </Button>
//           </TooltipTrigger>
//           <TooltipContent>Notifications{unreadCount > 0 ? ` (${unreadCount} unread)` : ""}</TooltipContent>
//         </Tooltip>
//         <ThemeToggle />
//         <DropdownMenu>
//           <Tooltip>
//             <TooltipTrigger asChild>
//               <DropdownMenuTrigger asChild>
//                 <Button variant="ghost" size="icon" aria-label="User menu">
//                   <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
//                     {initials(user?.name)}
//                   </span>
//                 </Button>
//               </DropdownMenuTrigger>
//             </TooltipTrigger>
//             <TooltipContent>Account &amp; sign out</TooltipContent>
//           </Tooltip>
//           <DropdownMenuContent align="end">
//           <DropdownMenuLabel>
//             <div className="flex flex-col">
//               <span className="text-sm font-medium">{user?.name ?? "User"}</span>
//               <span className="text-xs text-muted-foreground">{user?.email}</span>
//             </div>
//           </DropdownMenuLabel>
//           <DropdownMenuSeparator />
//           <DropdownMenuItem onClick={() => void logout()} destructive>
//             <LogOut className="h-4 w-4" /> Sign out
//           </DropdownMenuItem>
//           </DropdownMenuContent>
//         </DropdownMenu>
//       </div>
//     </header>
//   );
// }

/**
 * Topbar.tsx — sticky top bar with mobile menu toggle, theme switcher, and
 * user menu.
 */
import { Bell, HelpCircle, LogOut, Menu, User } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/context/AuthContext";
import { http } from "@/services/apiClient";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ThemeToggle } from "@/components/ThemeToggle";
import { initials } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function Topbar({ onMenuClick }: { onMenuClick?: () => void }) {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // SH-4 — keyboard shortcut: press ? to open Help Guide
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      // Ignore when typing in an input, textarea, or select
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "?") {
        e.preventDefault();
        navigate("/help-guide");
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [navigate]);

  // Notification bell — Help Guide §Compliance: "notification bell widget"
  const { data: notifData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => http.get<{ unread_count: number }>("/api/v1/notifications/unread-count").catch(() => ({ unread_count: 0 })),
    enabled: isAuthenticated,
    staleTime: 30_000,
  });
  const unreadCount = notifData?.unread_count ?? 0;

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={onMenuClick}
              aria-label="Toggle navigation"
            >
              <Menu className="h-5 w-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Toggle navigation</TooltipContent>
        </Tooltip>
        <div className="hidden sm:block">
          <p className="text-sm font-medium">Welcome back, {user?.name ?? "User"}</p>
          <p className="text-xs text-muted-foreground">
            {user?.email}
            {user?.tenantSlug ? ` · ${user.tenantSlug}` : " · platform"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {user && (
          <Badge variant="secondary" className="hidden sm:inline-flex">
            {user.role.replace("_", " ")}
          </Badge>
        )}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Help guide" asChild>
              <Link to="/help-guide">
                <HelpCircle className="h-5 w-5" />
              </Link>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Help Guide — docs &amp; walkthroughs</TooltipContent>
        </Tooltip>
        {/* Notification bell — Help Guide §Compliance */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Notifications" asChild>
              <Link to="/notifications" className="relative">
                <Bell className="h-5 w-5" />
                {unreadCount > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </Link>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Notifications{unreadCount > 0 ? ` (${unreadCount} unread)` : ""}</TooltipContent>
        </Tooltip>
        <ThemeToggle />
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="User menu">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                    {initials(user?.name)}
                  </span>
                </Button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent>Account &amp; sign out</TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="end">
          <DropdownMenuLabel>
            <div className="flex flex-col">
              <span className="text-sm font-medium">{user?.name ?? "User"}</span>
              <span className="text-xs text-muted-foreground">{user?.email}</span>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link to="/profile" className="flex items-center gap-2 cursor-pointer">
              <User className="h-4 w-4" /> My Profile
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => void logout()} destructive>
            <LogOut className="h-4 w-4" /> Sign out
          </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}