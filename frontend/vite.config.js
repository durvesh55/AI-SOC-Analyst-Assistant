import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to Vite (port 5173) and Vite forwards /api/* to FastAPI,
// so there are no cross-origin requests. Change VITE_PROXY_TARGET if the backend uses another port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_PROXY_TARGET || "http://127.0.0.1:8001", changeOrigin: true } },
    },
  };
});
