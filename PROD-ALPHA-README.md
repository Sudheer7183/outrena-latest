# OUTRENA — Production Alpha Release Notes

**Version:** v1.0 Alpha  
**Package:** OUTRENA-Production-Alpha-v1  
**Baseline:** OUTRENA-Migration-Phase6-SaaS-v8  
**Date:** 2026-07-26

---

## What Changed in This Release

This package applies production hardening on top of the Phase 6 SaaS v8 codebase. All changes are backward-compatible and additive — no existing functionality was removed or broken.

### PROD-1 · Real Outrena Logo in Sidebar

**File:** `outrena-frontend/src/components/layout/Sidebar.tsx`

The placeholder `O` text mark has been replaced with the actual Outrena horizontal lockup PNG. The logo switches automatically between the light and dark variants using `next-themes`' `resolvedTheme`.

### PROD-2 · Real Outrena Logo on Login Page

**File:** `outrena-frontend/src/features/auth/LoginPage.tsx`

The generic Sparkles icon on the login card has been replaced with the Outrena lockup in its dark-mode variant (the login page background is always dark slate).

### PROD-3 · Bundle Splitting (1.94 MB → ~10 chunks)

**File:** `outrena-frontend/vite.config.ts`

Added `rollupOptions.output.manualChunks` splitting the previously single 1.94 MB bundle into 10 named chunks:

| Chunk | Contents |
|---|---|
| `vendor-react` | React, ReactDOM, React Router |
| `vendor-query` | TanStack Query |
| `vendor-radix` | All Radix UI primitives |
| `vendor-charts` | Recharts |
| `vendor-dnd` | @dnd-kit (Deals Kanban) |
| `vendor-motion` | Framer Motion |
| `vendor-auth` | Keycloak JS |
| `vendor-analytics` | PostHog JS |
| `vendor-forms` | react-hook-form, zod |
| `vendor-md` | react-markdown, remark-gfm |
| `brand-assets` | Base64 logo assets (isolated — largest single module) |

**Impact:** Faster parse on first load; vendor chunks are aggressively cached between deploys.

### PROD-4 · Real Favicon + Alpha Robots Tag

**Files:** `outrena-frontend/index.html`, `outrena-frontend/public/favicon.png`

- Replaced placeholder `favicon.svg` with the real `Outrena_Favicon_32.png`
- Added `<meta name="robots" content="noindex, nofollow">` so alpha testers' instances are not indexed by search engines

### PROD-5 · Missing `/api/v1/meetings` CRUD Router

**File:** `outrena-backend/app/features/meetings/meetings_router.py` *(new)*

The `MeetingsPage.tsx` called `GET/POST/PATCH/DELETE /api/v1/meetings` but no backend router existed — every request to the Meetings page resulted in a 404. This router is now present:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/meetings` | List meetings (optional `status`, `prospectId` filters) |
| POST | `/api/v1/meetings` | Create meeting (201) |
| GET | `/api/v1/meetings/{id}` | Fetch one |
| PATCH | `/api/v1/meetings/{id}` | Partial update |
| DELETE | `/api/v1/meetings/{id}` | Delete (204) |

The router is auto-discovered by `app/api/v1/__init__.py` via `pkgutil`. No changes to `main.py` required.

### PROD-6 · Brand Assets Module

**File:** `outrena-frontend/src/lib/brand-assets.ts` *(new)*

Central module exporting three base64-embedded brand assets:
- `LOGO_LIGHT` — 2000×384 light lockup PNG
- `LOGO_DARK` — 2000×384 dark lockup PNG  
- `APP_ICON` — 512×512 app icon PNG

Inlined as data URIs so the logo renders without any network request in every deployment environment.

### PROD-7 · OutrenaLogo Component

**File:** `outrena-frontend/src/components/OutrenaLogo.tsx` *(new)*

Two exported components:
- `<OutrenaLockup width={n} />` — horizontal wordmark, auto-switches light/dark
- `<OutrenaIcon size={n} />` — square app icon

---

## Already-Fixed Items Verified in This Audit

The following audit issues were reported as RESIDUAL in v8 but are confirmed **already fixed** in the v8 codebase:

| Issue | Status |
|---|---|
| **E2** — `send_email()` passed `to=""` (null-recipient sends) | ✅ Fixed in v8 — code reads Prospect email from DB and decrypts via PiiService |
| **E6** — 7-touch cadence not auto-generating Sequence rows | ✅ Fixed in v8 — `generate_cadence_for_campaign()` invoked on `link_prospect()` |

Both are covered by the new test suite.

---

## Architecture Notes

- **Meetings router auto-discovery**: The new `meetings_router.py` is placed in `app/features/meetings/` alongside the existing `router.py` (meeting-prep). Both are discovered by `pkgutil.iter_modules`. If you ever see only 4 meeting endpoints instead of 5+5, check that `meetings_router.py` is present and has no import errors.

- **Logo asset size**: The `brand-assets.ts` file is ~78 KB. It is isolated into its own Vite chunk (`brand-assets`) so it does not inflate the initial app bundle. It is only loaded when a component that imports from it is rendered.

- **Dark mode logo**: `OutrenaLockup` uses `next-themes`' `useTheme()`. On the login page (always dark), the component is called directly with the dark-mode variant; on the sidebar it switches automatically.

---

## Known Residual Issues (Not Fixed — Documented)

These are feature-completion items from the v8 audit that are **out of scope** for this alpha-hardening pass:

| ID | Description | Priority for Alpha |
|---|---|---|
| E3 | `ReplyDraft` not auto-created on reply webhook — manual triage only | LOW — manual triage still works |
| E4 | `UsageService` not called for email/enrich/LinkedIn events — only LLM calls tracked | LOW — LLM cost tracking works |
| E5 | `CostSummary` rollup never triggered — data stays in `usage_events` raw | LOW — raw data accessible |
| E8 | Autopilot LLM calls attributed to `_unknown` tenant | MEDIUM — fix before billing goes live |

---

## Applying This Package

```bash
# 1. Extract the ZIP
unzip OUTRENA-Production-Alpha-v1.zip -d outrena-alpha

# 2. Start the stack
cd outrena-alpha
cp outrena-backend/.env.example outrena-backend/.env
# Edit .env — set ENCRYPTION_KEY at minimum
docker compose up -d

# 3. Verify backend
curl http://localhost:8000/health | jq
# Expected: {"status":"ok","checks":{"db":{"status":"up"},...}}

# 4. Verify meetings route is present
curl http://localhost:8000/openapi.json | python3 -c "
import json,sys
paths = json.load(sys.stdin)['paths']
print([p for p in paths if 'meetings' in p])
"
# Expected: ['/api/v1/meetings', '/api/v1/meetings/{meeting_id}', '/api/v1/meeting-prep', ...]

# 5. Open frontend
open http://localhost:5173
```

---

## Test Package

See `tests/production/README.md` for instructions on running the production test suite.
