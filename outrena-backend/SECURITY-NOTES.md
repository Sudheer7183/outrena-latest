# OUTRENA — Security Design Notes

## CSRF Protection (URD NFR-018) — Satisfied by Design

NFR-018 requires CSRF protection on state-changing browser requests. OUTRENA
satisfies this architecturally rather than with per-request CSRF tokens:

1. **Bearer-token-only authentication.** The API accepts credentials solely
   via the `Authorization: Bearer <JWT>` header (see `app/api/security.py`).
   No authentication cookie exists, so a cross-site attacker's forged request
   carries no credentials — the classic CSRF vector requires ambient cookie
   auth, which this API does not use.
2. **Tokens live in JS memory, not cookies.** `keycloak-js` holds tokens in
   memory (`AuthContext.applyToken`); nothing auto-attaches to cross-origin
   requests.
3. **CORS allow-list.** `CORSMiddleware` restricts browser origins to
   `*.{BASE_DOMAIN}` — cross-origin XHR from an attacker page is blocked at
   the preflight.
4. **State-changing public endpoints** (DSR submission, unsubscribe) are
   unauthenticated by design (GDPR requirement), rate-limited at the edge
   (nginx `auth` zone, 5 r/s), and idempotent — a forged submission has the
   same effect as a legitimate one and exposes no data.

Per OWASP's CSRF Prevention Cheat Sheet, token-based (non-cookie) session
management is a complete CSRF mitigation; no synchronizer tokens are needed.
If cookie-based sessions are ever introduced, this decision MUST be revisited
and `SameSite=Strict` + synchronizer tokens added.

## MFA (URD NFR-015 / FR-090)

TOTP-based MFA is enforced for TENANT_ADMIN and SUPER_ADMIN:
- Realm OTP policy: `keycloak/realm-export.json` (`otpPolicyType: totp`).
- New admin users are created with the `CONFIGURE_TOTP` required action
  (`keycloak_admin_service.create_tenant_admin_user`,
  `user_management/service.create_user`).
- Promotion to an admin role adds `CONFIGURE_TOTP` on the next login
  (`user_management/service.update_user`).
