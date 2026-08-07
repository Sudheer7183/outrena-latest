# OUTRENA Frontend — Phase 1 (Foundation scaffold)

> **Phase 1 goal**: Stand up the frontend skeleton — Vite + React 18 + TypeScript,
> minimal health-check page that calls the FastAPI `/health` endpoint. The full
> SPA (33 pages, Keycloak auth, react-router) is delivered in Phase 5.

## Stack

| Layer            | Technology                              |
|------------------|-----------------------------------------|
| Framework        | React 18 + Vite 6                       |
| Language         | TypeScript 5                            |
| Routing (Ph 5)   | react-router v6                         |
| Server state     | TanStack Query 5                        |
| Client state     | Zustand 5                               |
| HTTP             | axios 1                                 |
| Auth (Ph 5)      | keycloak-js (OIDC + PKCE)               |
| Styling          | Tailwind CSS 3 + tailwindcss-animate    |
| Forms (Ph 5)     | react-hook-form + zod                   |
| Components (Ph 5)| shadcn/ui (lucide-react, cva, sonner)   |
| Build            | Vite (esbuild)                          |

## Phase 1 layout

```
outrena-frontend/
├── public/
│   └── favicon.svg
├── src/
│   ├── App.tsx              # Phase 1 health-check page
│   ├── main.tsx             # Vite entry — mounts <App/>
│   ├── index.css            # Tailwind base + design tokens
│   └── vite-env.d.ts        # Vite env var types
├── index.html               # Vite HTML shell
├── package.json
├── tsconfig.json
├── vite.config.ts           # Dev server + API proxy
├── tailwind.config.ts
├── postcss.config.js
├── eslint.config.js
├── .prettierrc.json
├── Dockerfile               # Multi-stage: builder + nginx:alpine
├── nginx-frontend.conf      # SPA fallback + /api proxy
├── .dockerignore
├── .env.example
├── .gitignore
└── README.md                # this file
```

## Quick start (local dev)

### Option A — Docker Compose (recommended)

From the migration root (parent of this folder):

```bash
docker compose up -d
open http://localhost:5173
```

### Option B — Native Node

```bash
cd outrena-frontend
npm install
cp .env.example .env
npm run dev
open http://localhost:5173
```

The Phase 1 page will show the backend's `/health` response with per-service
status (db, redis, keycloak).

## Scripts

| Script              | Purpose                                  |
|---------------------|------------------------------------------|
| `npm run dev`       | Vite dev server (port 5173, HMR)         |
| `npm run build`     | `tsc -b && vite build` → `dist/`         |
| `npm run preview`   | Preview the production build             |
| `npm run typecheck` | `tsc --noEmit`                           |
| `npm run lint`      | ESLint                                   |
| `npm run format`    | Prettier write                           |

## Dev-server proxy

`vite.config.ts` proxies the following paths to avoid CORS during local dev:

| Path        | Target                       |
|-------------|------------------------------|
| `/api`      | `http://localhost:8000`      |
| `/platform` | `http://localhost:8000`      |
| `/auth`     | `http://localhost:8080` (Keycloak, rewritten) |
| `/health`   | `http://localhost:8000`      |

## What's NOT in Phase 1

The following arrive in Phase 5 (Frontend Migration):

- `src/main.tsx` — BrowserRouter + AuthProvider + QueryClientProvider + Toaster
- `src/features/{name}/pages/` — 33 page components
- `src/components/ui/` — shadcn/ui component library
- `src/lib/api-client.ts` — axios + auth interceptor
- `src/lib/auth.tsx` — Keycloak JS adapter
- `src/lib/store.ts` — Zustand store
- `src/components/layout/Sidebar.tsx`, `Topbar.tsx`
- `src/routes.tsx` — protected routes + role gating
- `src/features/*/api/*.ts` — typed service layer per feature

## Source mapping

This frontend is a faithful migration of:
- `src/app/page.tsx` (Next.js single-page app with `onNavigate`) → 33 route components
- `src/components/ui/*` (shadcn/ui) → identical components, ported verbatim
- `src/lib/*` (Zustand store, fetch wrappers) → `src/lib/*` + axios service layer
- NextAuth client → Keycloak JS adapter
