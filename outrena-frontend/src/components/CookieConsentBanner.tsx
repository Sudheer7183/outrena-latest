/**
 * CookieConsentBanner.tsx — fixed-bottom GDPR cookie consent banner.
 *
 * Renders on public pages (mounted inside <PublicLayout>). Persists the user's
 * consent choice in localStorage under `outrena:cookie-consent`. Supports:
 *   - Accept all (necessary + analytics + marketing)
 *   - Necessary only
 *   - Customize (dialog with per-category toggles)
 *
 * If the user has already answered, the banner is not shown. To re-prompt,
 * clear the localStorage key (or call `window.resetCookieConsent()`).
 */
import { useEffect, useState } from "react";
import { Cookie, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const STORAGE_KEY = "outrena:cookie-consent";
const STORAGE_VERSION = "v1";

type ConsentChoice = {
  version: string;
  necessary: true; // always required
  analytics: boolean;
  marketing: boolean;
  answeredAt: string;
};

const DEFAULT_CHOICE: Omit<ConsentChoice, "answeredAt"> = {
  version: STORAGE_VERSION,
  necessary: true,
  analytics: false,
  marketing: false,
};

function loadConsent(): ConsentChoice | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ConsentChoice;
    if (parsed.version !== STORAGE_VERSION) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveConsent(choice: Omit<ConsentChoice, "answeredAt">): ConsentChoice {
  const full: ConsentChoice = { ...choice, answeredAt: new Date().toISOString() };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(full));
  } catch {
    // localStorage unavailable (private mode) — no-op; banner will re-appear.
  }
  return full;
}

// Expose a reset helper for testing / settings page.
declare global {
  interface Window {
    resetCookieConsent?: () => void;
  }
}

export function CookieConsentBanner() {
  const [visible, setVisible] = useState(false);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [draft, setDraft] = useState<Omit<ConsentChoice, "answeredAt">>(DEFAULT_CHOICE);

  useEffect(() => {
    const existing = loadConsent();
    if (!existing) {
      // Slight delay so the banner doesn't feel jarring on first paint.
      const t = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(t);
    }
    // If we already have consent, fire a one-shot event so analytics scripts
    // can bootstrap themselves. (Future: this could also gate script loading.)
    window.dispatchEvent(
      new CustomEvent("outrena:cookie-consent", { detail: existing }),
    );
    setVisible(false);
    return undefined;
  }, []);

  // Expose reset helper.
  useEffect(() => {
    window.resetCookieConsent = () => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
      setDraft(DEFAULT_CHOICE);
      setVisible(true);
    };
    return () => {
      delete window.resetCookieConsent;
    };
  }, []);

  function acceptAll() {
    const choice = saveConsent({
      version: STORAGE_VERSION,
      necessary: true,
      analytics: true,
      marketing: true,
    });
    window.dispatchEvent(
      new CustomEvent("outrena:cookie-consent", { detail: choice }),
    );
    setVisible(false);
  }

  function necessaryOnly() {
    const choice = saveConsent(DEFAULT_CHOICE);
    window.dispatchEvent(
      new CustomEvent("outrena:cookie-consent", { detail: choice }),
    );
    setVisible(false);
  }

  function saveCustomized() {
    const choice = saveConsent(draft);
    window.dispatchEvent(
      new CustomEvent("outrena:cookie-consent", { detail: choice }),
    );
    setCustomizeOpen(false);
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <>
      <div
        role="dialog"
        aria-label="Cookie consent"
        className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background/95 p-4 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-background/80"
      >
        <div className="mx-auto flex max-w-7xl flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 hidden rounded-md bg-primary/10 p-2 text-primary sm:block">
              <Cookie className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold">
                We use cookies for analytics and functionality.
              </p>
              <p className="text-xs text-muted-foreground">
                Necessary cookies are always required. You can opt in to
                analytics and marketing cookies below. See our{" "}
                <a
                  href="/p/privacy"
                  className="font-medium text-foreground hover:underline"
                >
                  Privacy Policy
                </a>{" "}
                for details.
              </p>
            </div>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <Button variant="outline" size="sm" onClick={() => setCustomizeOpen(true)}>
              Customize
            </Button>
            <Button variant="ghost" size="sm" onClick={necessaryOnly}>
              Necessary only
            </Button>
            <Button size="sm" onClick={acceptAll}>
              Accept all
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={customizeOpen} onOpenChange={setCustomizeOpen}>
        <DialogClose onClose={() => setCustomizeOpen(false)} />
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            Customize Cookie Consent
          </DialogTitle>
          <DialogDescription>
            Choose which cookie categories to enable. Necessary cookies are
            always on.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <ConsentToggle
            label="Necessary"
            description="Required for the site to function (auth, security, session). Cannot be disabled."
            checked
            disabled
          />
          <ConsentToggle
            label="Analytics"
            description="Anonymous usage statistics that help us improve the product."
            checked={draft.analytics}
            onChange={(v) => setDraft({ ...draft, analytics: v })}
          />
          <ConsentToggle
            label="Marketing"
            description="Personalized marketing cookies (e.g., retargeting pixels)."
            checked={draft.marketing}
            onChange={(v) => setDraft({ ...draft, marketing: v })}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setCustomizeOpen(false)}>
            Cancel
          </Button>
          <Button onClick={saveCustomized}>Save preferences</Button>
        </DialogFooter>
      </Dialog>
    </>
  );
}

function ConsentToggle({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange?: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div className="space-y-0.5">
        <Label htmlFor={`cc-${label}`} className="text-sm font-medium">
          {label}
        </Label>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch
        id={`cc-${label}`}
        checked={checked}
        onCheckedChange={(v) => onChange?.(v)}
        disabled={disabled}
      />
    </div>
  );
}
