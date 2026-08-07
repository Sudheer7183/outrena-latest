/**
 * OnboardingChecklist.tsx — Post-login guided onboarding modal (FR-E1-007/008).
 *
 * Shown once after first login until all 6 items are complete or the user
 * explicitly dismisses. State persisted to localStorage under "outrena:onboarding:dismissed".
 *
 * The 6 items: create ICP → connect MailBridge → verify domain →
 *              import prospects → create campaign → send first email.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, X, ChevronRight, Sparkles } from "lucide-react";
import { http } from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface ChecklistItem {
  key: string;
  label: string;
  description: string;
  link: string;
  order: number;
  done: boolean;
}

interface ChecklistData {
  items: ChecklistItem[];
  completed: number;
  total: number;
  all_done: boolean;
}

const DISMISSED_KEY = "outrena:onboarding:dismissed";

export function OnboardingChecklist() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  // Only show for authenticated users who haven't dismissed
  const dismissed = typeof window !== "undefined"
    ? localStorage.getItem(DISMISSED_KEY) === "true"
    : true;

  const { data, isSuccess } = useQuery<ChecklistData>({
    queryKey: ["onboarding-checklist"],
    queryFn: () => http.get("/api/v1/onboarding/checklist"),
    enabled: isAuthenticated && !dismissed,
    staleTime: 30_000,
  });

  // Open the modal once data loads and checklist isn't complete yet
  useEffect(() => {
    if (isSuccess && data && !data.all_done && !dismissed) {
      setOpen(true);
    }
  }, [isSuccess, data, dismissed]);

  function handleDismiss() {
    localStorage.setItem(DISMISSED_KEY, "true");
    setOpen(false);
  }

  function handleNavigate(link: string) {
    setOpen(false);
    navigate(link);
  }

  if (!isAuthenticated || dismissed || !data) return null;

  const pct = Math.round((data.completed / data.total) * 100);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) setOpen(false); }}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <DialogTitle>Get started with OUTRENA</DialogTitle>
            </div>
            <Button variant="ghost" size="icon" onClick={handleDismiss} className="h-6 w-6 rounded-full">
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <DialogDescription>
            Complete these {data.total} steps to send your first campaign.{" "}
            <span className="font-medium text-foreground">
              {data.completed}/{data.total} done
            </span>
          </DialogDescription>
          <Progress value={pct} className="mt-2 h-1.5" />
        </DialogHeader>

        <div className="space-y-1 pt-2">
          {data.items.map((item) => (
            <button
              key={item.key}
              onClick={() => !item.done && handleNavigate(item.link)}
              disabled={item.done}
              className={cn(
                "w-full flex items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors",
                item.done
                  ? "opacity-60 cursor-default"
                  : "hover:bg-accent cursor-pointer"
              )}
            >
              {/* Step number / check */}
              <div className="mt-0.5 shrink-0">
                {item.done ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                ) : (
                  <div className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-muted-foreground/40">
                    <span className="text-[10px] font-semibold text-muted-foreground">
                      {item.order}
                    </span>
                  </div>
                )}
              </div>
              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className={cn("text-sm font-medium", item.done && "line-through text-muted-foreground")}>
                  {item.label}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                  {item.description}
                </p>
              </div>
              {/* Arrow */}
              {!item.done && (
                <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              )}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <button
            onClick={handleDismiss}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip for now
          </button>
          {data.completed > 0 && (
            <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
              🎉 Great progress — keep going!
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}