import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // Proxy API calls to the orchestrator so the browser hits one origin.
      "/api": {
        target: process.env.ORCHESTRATOR_URL || "http://orchestrator:8080",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
