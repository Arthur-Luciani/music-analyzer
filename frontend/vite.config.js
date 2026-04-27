import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendOrigin = process.env.VITE_BACKEND_ORIGIN || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: backendOrigin,
        changeOrigin: true,
      },
      "/ws": {
        target: backendOrigin,
        ws: true,
        changeOrigin: true,
      },
      "/health": {
        target: backendOrigin,
        changeOrigin: true,
      },
    },
  },
});
