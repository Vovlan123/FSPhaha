import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В разработке API и mock ФСП проксируются на бэкенд, поэтому фронтенд ходит по относительным путям.
const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": backend, "/fsp": backend },
  },
  preview: {
    host: true,
    port: 4173,
  },
});
