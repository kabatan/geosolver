import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  build: {
    outDir: "dist/client",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/katex/")) return "math-renderer";
          if (id.includes("/node_modules/@phosphor-icons/")) return "icons";
          if (
            id.includes("/node_modules/react/") ||
            id.includes("/node_modules/react-dom/") ||
            id.includes("/node_modules/scheduler/")
          )
            return "react-vendor";
        },
      },
    },
  },
  optimizeDeps: { include: ["react", "react-dom/client"] },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local", "localhost", "127.0.0.1"],
    warmup: { clientFiles: ["./src/main.tsx"] },
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  plugins: [react()],
});
