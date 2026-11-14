import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The embeddable chat widget: one self-contained script that store owners
// add to their site with a single <script> tag.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      // Preact's React compatibility layer keeps the embedded widget small:
      // store owners load this script on every page of their site.
      react: "preact/compat",
      "react-dom": "preact/compat",
      "react-dom/client": "preact/compat/client",
      "react/jsx-runtime": "preact/jsx-runtime",
    },
  },
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    outDir: "../src/support_agent/web/dist",
    emptyOutDir: false,
    lib: {
      entry: fileURLToPath(new URL("./src/widget/main.tsx", import.meta.url)),
      name: "SupportWidget",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
  },
});
