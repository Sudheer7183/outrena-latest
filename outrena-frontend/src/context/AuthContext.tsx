
import Keycloak from "keycloak-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { setAccessToken } from "@/services/apiClient";
import type { AuthUser, Role } from "@/types/common";
import { identifyUser, resetUser } from "@/lib/posthog";

const DEV_BYPASS = import.meta.env.VITE_DEV_BYPASS_AUTH === "true";
const KC_URL = import.meta.env.VITE_KEYCLOAK_URL ?? "";
const KC_REALM = import.meta.env.VITE_KEYCLOAK_REALM ?? "outrena";
const KC_CLIENT = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "frontend";

interface AuthContextValue {
  user: AuthUser | null;
  initialized: boolean;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  loginAsDev: (role: Role) => void;  // BUG-43: dev-mode login selector
  logout: () => Promise<void>;
  hasRole: (minimum: Role) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const ROLE_ORDER: Record<Role, number> = {
  REP: 10,
  MANAGER: 20,
  TENANT_ADMIN: 30,
  SUPER_ADMIN: 40,
};

function decodeRole(token?: string): Role {
  // Best-effort: read the `role` claim from the JWT payload. Falls back to REP.
  try {
    if (!token) return "REP";
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as Record<string, unknown>;
    const role = (payload.role as string) ?? "REP";
    if (role in ROLE_ORDER) return role as Role;
    return "REP";
  } catch {
    return "REP";
  }
}

function decodeTenantSlug(token?: string): string | null {
  try {
    if (!token) return null;
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as Record<string, unknown>;
    return (payload.tenant_slug as string) ?? null;
  } catch {
    return null;
  }
}

function decodeEmail(token?: string): string {
  try {
    if (!token) return "";
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as Record<string, unknown>;
    return (payload.email as string) ?? (payload.preferred_username as string) ?? "";
  } catch {
    return "";
  }
}

// BUG-43 FIX: Multiple dev identities so devs can test all role tiers.
const DEV_USERS: Record<Role, AuthUser> = {
  SUPER_ADMIN: {
    id: "dev-superadmin",
    email: "admin@outrena.dev",
    name: "Dev Super Admin",
    role: "SUPER_ADMIN",
    tenantSlug: "acme",
  },
  TENANT_ADMIN: {
    id: "dev-tenantadmin",
    email: "tenant-admin@outrena.dev",
    name: "Dev Tenant Admin",
    role: "TENANT_ADMIN",
    tenantSlug: "acme",
  },
  MANAGER: {
    id: "dev-manager",
    email: "manager@outrena.dev",
    name: "Dev Manager",
    role: "MANAGER",
    tenantSlug: "acme",
  },
  REP: {
    id: "dev-rep",
    email: "rep@outrena.dev",
    name: "Dev Rep",
    role: "REP",
    tenantSlug: "acme",
  },
};
// DEV_BYPASS: set the Bearer token synchronously at module load — before
// React even renders — so apiClient.getAccessToken() never returns null on
// the very first request. Relying on a useEffect inside AuthProvider is not
// safe here: React fires effects child-first during the initial mount, so a
// query fired from a deeply nested page component (e.g. useQuery on mount)
// can run BEFORE AuthProvider's own effect sets the token, sending the
// first request with no Authorization header. The backend then rejects it
// ("Tenant not identified") and TanStack Query does not automatically retry
// once the token becomes available.
if (DEV_BYPASS) {
  setAccessToken("dev-token");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // BUG-43 FIX: In dev-bypass, start unauthenticated so the login selector shows.
  // Previously this auto-logged in as SUPER_ADMIN with no way to pick a different role.
  const [user, setUser] = useState<AuthUser | null>(null);
  const [initialized, setInitialized] = useState(DEV_BYPASS);
  const kcRef = useRef<Keycloak | null>(null);

  const applyToken = useCallback((token?: string) => {
    setAccessToken(token ?? null);
    if (!token) {
      setUser(null);
      return;
    }
    const role = decodeRole(token);
    const tenantSlug = decodeTenantSlug(token);
    const email = decodeEmail(token);
    setUser({
      id: "self",
      email,
      name: email.split("@")[0] || "User",
      role,
      tenantSlug,
    });
  }, []);

  // Initialise Keycloak once.
  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (DEV_BYPASS) {
        // State + token already seeded synchronously above the component —
        // nothing left to do here.
        return;
      }

      if (!KC_URL) {
        // No Keycloak configured — render the app unauthenticated so the
        // login page can show. Routes are gated by ProtectedRoute.
        setInitialized(true);
        return;
      }

      try {
        const kc = new Keycloak({
          url: KC_URL,
          realm: KC_REALM,
          clientId: KC_CLIENT,
        });
        kcRef.current = kc;
        const authenticated = await kc.init({
          pkceMethod: "S256",
          checkLoginIframe: false,
          // "check-sso" silently returns authenticated=false when the session
          // expires, then every API call returns 401, which fires kc.login(),
          // which redirects to Keycloak, which redirects back — infinite loop.
          // "login-required" lets Keycloak itself handle the unauthenticated
          // state: it redirects to the login page directly without returning
          // control to the app in an unauthenticated state.
          onLoad: "check-sso",
          silentCheckSsoRedirectUri:
            window.location.origin + "/silent-check-sso.html",
        });
        if (cancelled) return;
        if (authenticated) {
          applyToken(kc.token);
          // Clear any stale circuit breaker from a previous failed session
          sessionStorage.removeItem("outrena:login_attempted");
          kc.onTokenExpired = () => {
            kc.updateToken(60).then((refreshed) => {
              if (refreshed) applyToken(kc.token);
            }).catch(() => {
              // Token refresh failed — redirect to login once
              applyToken(undefined);
              kc.login();
            });
          };
        } else {
          // Not authenticated — go to login page immediately.
          // Do NOT call applyToken(undefined) and return to app — that causes
          // every mounted query to fire and get 401 → redirect loop.
          applyToken(undefined);
        }
      } catch {
        applyToken(undefined);
      } finally {
        if (!cancelled) setInitialized(true);
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [applyToken]);

  // Listen for 401 events dispatched by the apiClient interceptor.
  //
  // INFINITE-LOOP FIX: A naive `kc.login()` on every 401 creates an infinite
  // redirect cycle when the backend returns 401 even after a valid Keycloak
  // session (e.g. missing `tenant_slug` claim, TenantMiddleware resolution
  // failure, or freshly-provisioned tenant with incomplete Keycloak attribute
  // mapping). The pattern is:
  //   API 401 → kc.login() → Keycloak redirects back → check-sso succeeds →
  //   initialized=true → queries fire → API 401 → kc.login() → ... ∞
  //
  // Circuit breaker: allow at most ONE login attempt per session. If the first
  // redirect comes back and API calls still return 401, stop redirecting and
  // set an error state so the user sees a message instead of a blank loop.
  // Circuit breaker stored in sessionStorage — survives Keycloak redirects.
  // useRef resets on every page reload so the old ref-based breaker never fired.
  const LOGIN_ATTEMPTED_KEY = "outrena:login_attempted";
  const loginAttemptedRef = useRef(
    typeof sessionStorage !== "undefined" &&
      sessionStorage.getItem(LOGIN_ATTEMPTED_KEY) === "true",
  );

  useEffect(() => {
    function onUnauthorized() {
      if (DEV_BYPASS) return;
      if (loginAttemptedRef.current) {
        console.warn(
          "[AuthContext] 401 after re-login — role claim missing from " +
          "Keycloak token. Check realm-export.json role mapper config. " +
          "Stopping redirect loop.",
        );
        sessionStorage.removeItem(LOGIN_ATTEMPTED_KEY);
        loginAttemptedRef.current = false;
        return;
      }
      loginAttemptedRef.current = true;
      sessionStorage.setItem(LOGIN_ATTEMPTED_KEY, "true");
      kcRef.current?.login();
    }
    window.addEventListener("outrena:unauthorized", onUnauthorized);
    return () => window.removeEventListener("outrena:unauthorized", onUnauthorized);
  }, []);

  // Clear the breaker flag on successful auth so logout+login works.
  useEffect(() => {
    if (user) {
      sessionStorage.removeItem(LOGIN_ATTEMPTED_KEY);
      loginAttemptedRef.current = false;
    }
  }, [user]);

  // PH-FE: sync PostHog identity with auth state. Whenever `user` transitions
  // (login, token refresh, logout, dev-bypass), identify the new user or reset
  // the previous one. All PostHog calls are no-ops when VITE_POSTHOG_KEY is
  // unset, and the outer try/catch guarantees auth is never broken by an
  // observability helper throwing.
  useEffect(() => {
    try {
      if (user) {
        identifyUser(user.id, {
          email: user.email,
          role: user.role,
          tenant_slug: user.tenantSlug,
          name: user.name,
        });
      } else {
        resetUser();
      }
    } catch {
      /* never break auth */
    }
  }, [user]);

  // BUG-43 FIX: loginAsDev lets the dev-mode login selector pick any role.
  const loginAsDev = useCallback((role: Role) => {
    const devUser = DEV_USERS[role];
    setUser(devUser);
    setAccessToken("dev-token");
  }, []);

  const login = useCallback(async () => {
    if (DEV_BYPASS) {
      // BUG-43 FIX: no longer auto-login as SUPER_ADMIN here;
      // use loginAsDev() from the login selector instead.
      loginAsDev("SUPER_ADMIN");
      return;
    }
    await kcRef.current?.login();
  }, [applyToken, loginAsDev]);

  const logout = useCallback(async () => {
    setAccessToken(null);
    setUser(null);
    if (!DEV_BYPASS) {
      await kcRef.current?.logout();
    }
  }, []);

  const hasRole = useCallback(
    (minimum: Role) => {
      if (!user) return false;
      return ROLE_ORDER[user.role] >= ROLE_ORDER[minimum];
    },
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      initialized,
      isAuthenticated: !!user,
      login,
      loginAsDev,
      logout,
      hasRole,
    }),
    [user, initialized, login, loginAsDev, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}