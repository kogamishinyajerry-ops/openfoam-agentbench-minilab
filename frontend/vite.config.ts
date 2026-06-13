import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard runs entirely off the bundled demoRuns.json (replay mode), so it
// works with no backend. When the FastAPI backend is up, /api is proxied for the
// live "run" endpoint.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // recharts is legitimately ~520 kB on its own; it lives in its own cacheable
    // chunk (below), so the default 500 kB warning is noise here.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Split the heavy vendor libs into their own chunks so app code stays
        // small and the big, rarely-changing vendors cache independently.
        manualChunks: {
          charts: ["recharts"],
          motion: ["framer-motion"],
        },
      },
    },
  },
});
