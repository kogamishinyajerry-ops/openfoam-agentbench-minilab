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
});
