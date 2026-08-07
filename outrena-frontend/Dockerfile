# Dockerfile — OUTRENA frontend (React 18 + Vite)
#
# Stage 1: builder — npm ci + vite build → static dist/
# Stage 2: runtime — nginx:alpine serves the SPA + proxies /api to backend

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build

# Copy manifests first — better layer caching
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Copy sources
COPY . .

# Declare build-time env vars so Vite can bake them into the bundle
ARG VITE_DEV_BYPASS_AUTH=false
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_KEYCLOAK_URL=http://localhost:8080
ARG VITE_KEYCLOAK_REALM=outrena
ARG VITE_KEYCLOAK_CLIENT_ID=frontend

ENV VITE_DEV_BYPASS_AUTH=$VITE_DEV_BYPASS_AUTH \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL \
    VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM \
    VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

RUN npm run build

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Copy built static assets
COPY --from=builder /build/dist /usr/share/nginx/html

# Copy nginx config (SPA fallback + API proxy)
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]