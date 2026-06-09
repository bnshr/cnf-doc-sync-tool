import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../cnf_doc_sync_ui/static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://localhost:8090",
    },
  },
});
