import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Vite config — OUTRENA frontend
// Dev server: http://localhost:5173 (with --host 0.0.0.0 for Docker)
// API proxy: /api → http://localhost:8000 (avoids CORS in dev)
//             /platform → http://localhost:8000
//             /auth → http://localhost:8080 (Keycloak)
// PROD-3: Added manualChunks to split the 1.94 MB single bundle into
// vendor chunks, reducing initial parse time for alpha testers.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/platform": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/auth": {
        target: "http://localhost:8080",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/auth/, ""),
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022",
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          // React + router core
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          // TanStack Query
          "vendor-query": ["@tanstack/react-query"],
          // Radix UI primitives (bundled together — they're small individually)
          "vendor-radix": [
            "@radix-ui/react-alert-dialog",
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-scroll-area",
            "@radix-ui/react-select",
            "@radix-ui/react-slot",
            "@radix-ui/react-tabs",
            "@radix-ui/react-toast",
            "@radix-ui/react-tooltip",
          ],
          // Charts
          "vendor-charts": ["recharts"],
          // DnD kit (used by DealsKanban)
          "vendor-dnd": ["@dnd-kit/core", "@dnd-kit/sortable", "@dnd-kit/utilities"],
          // Animation
          "vendor-motion": ["framer-motion"],
          // Auth
          "vendor-auth": ["keycloak-js"],
          // Analytics
          "vendor-analytics": ["posthog-js"],
          // Forms + validation
          "vendor-forms": ["react-hook-form", "@hookform/resolvers", "zod"],
          // Markdown
          "vendor-md": ["react-markdown", "remark-gfm"],
          // Brand assets (largest single file — isolated to own chunk)
          "brand-assets": ["./src/lib/brand-assets"],
        },
      },
    },
  },
});
