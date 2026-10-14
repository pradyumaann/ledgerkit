import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // `ledgerkit serve` serves the built app from inside the Python package.
    outDir: "../src/ledgerkit/web_dist",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
