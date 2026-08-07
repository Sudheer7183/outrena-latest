/**
 * LoginPage.tsx — public sign-in page (Keycloak + dev-bypass).
 *
 * PROD-2: Updated with real Outrena branding — lockup logo replaces the
 * generic sparkle icon. Retains all auth logic unchanged.
 *
 * BUG-43: In dev-bypass mode, shows a login selector with multiple test
 * identities (SuperAdmin, Tenant Admin, Manager, Rep) so devs can test
 * all role tiers. Real Keycloak OIDC flow is still available.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, LogIn, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/types/common";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { OutrenaLockup } from "@/components/OutrenaLogo";

const DEV_BYPASS = import.meta.env.VITE_DEV_BYPASS_AUTH === "true";
const KC_URL = String(import.meta.env.VITE_KEYCLOAK_URL ?? "");

export function LoginPage() {
  const { login, loginAsDev, isAuthenticated, initialized } = useAuth();
  const navigate = useNavigate();
  const [signingIn, setSigningIn] = useState(false);

  useEffect(() => {
    if (initialized && isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [initialized, isAuthenticated, navigate]);

  async function handleSignIn() {
    setSigningIn(true);
    try {
      await login();
    } finally {
      setSigningIn(false);
    }
  }

  const showDevButton = DEV_BYPASS || !KC_URL;

  // BUG-43: Dev identity options for login selector
  const DEV_IDENTITIES: { role: Role; label: string; email: string }[] = [
    { role: "SUPER_ADMIN", label: "Super Admin", email: "admin@outrena.dev" },
    { role: "TENANT_ADMIN", label: "Tenant Admin", email: "tenant-admin@outrena.dev" },
    { role: "MANAGER", label: "Manager", email: "manager@outrena.dev" },
    { role: "REP", label: "Rep", email: "rep@outrena.dev" },
  ];

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4">
      {/* Decorative background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(60rem 40rem at 80% -10%, rgba(99,102,241,0.18), transparent 60%), radial-gradient(50rem 30rem at 10% 110%, rgba(16,185,129,0.14), transparent 60%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <Card className="relative z-10 w-full max-w-md border-slate-800 bg-slate-900/80 text-slate-100 shadow-2xl backdrop-blur">
        <CardHeader className="space-y-4 text-center">
          {/* Real Outrena lockup — always renders the dark-mode variant here
              because the login page background is always dark (slate-950). */}
          <div className="flex justify-center pt-2">
            <OutrenaLockup width={160} />
          </div>
          <CardDescription className="text-slate-400">
            AI-Powered Outreach Operating System
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {showDevButton ? (
            /* BUG-43 FIX: Dev-mode login selector with multiple test identities */
            <div className="space-y-3">
              <p className="text-center text-xs font-medium uppercase tracking-wider text-slate-400">
                Dev Mode — Select Identity
              </p>
              <div className="space-y-2">
                {DEV_IDENTITIES.map(({ role, label, email }) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => loginAsDev(role)}
                    className="flex w-full items-center justify-between rounded-md border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-left text-sm transition-colors hover:border-indigo-500/50 hover:bg-slate-800"
                  >
                    <span className="font-medium text-slate-200">{label}</span>
                    <span className="text-xs text-slate-500">{email}</span>
                  </button>
                ))}
              </div>
              {KC_URL && (
                <div className="relative pt-2">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-slate-700" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="bg-slate-900 px-2 text-slate-500">or</span>
                  </div>
                </div>
              )}
              {KC_URL && (
                <Button
                  className="w-full"
                  onClick={handleSignIn}
                  disabled={signingIn}
                  variant="outline"
                >
                  {signingIn ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <LogIn className="mr-2 h-4 w-4" />
                  )}
                  Sign in with SSO
                </Button>
              )}
            </div>
          ) : (
            <Button
              className="w-full"
              onClick={handleSignIn}
              disabled={signingIn}
            >
              {signingIn ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <LogIn className="mr-2 h-4 w-4" />
              )}
              Sign in with SSO
            </Button>
          )}
        </CardContent>

        <CardFooter className="flex flex-col gap-2 text-center text-xs text-slate-500">
          <div className="flex items-center justify-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Secured with Keycloak OIDC · PKCE flow</span>
          </div>
          <p>
            By signing in you agree to the{" "}
            <a href="/p/terms" className="underline hover:text-slate-300">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="/p/privacy" className="underline hover:text-slate-300">
              Privacy Policy
            </a>
            .
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
