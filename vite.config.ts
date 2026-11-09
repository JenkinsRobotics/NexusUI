import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import path from "node:path";

/**
 * Builds the station UI.
 *   framework only:  npx vite build                       -> framework/nexusui/ui_dist
 *   one app:         NEXUSUI_APP=apps/robot_fleet npx vite build -> apps/robot_fleet/ui_dist
 * An app build bundles framework widgets plus the app's own widgets/<type>/ui.tsx.
 * Usually you run this through:  nexusui build apps/<app>
 */
const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));
const app = process.env.NEXUSUI_APP ? path.resolve(process.env.NEXUSUI_APP) : null;
const engine = process.env.NEXUSUI_ENGINE ?? "http://localhost:8000";

export default defineConfig({
  root: here("./framework/ui"),
  base: "./",
  plugins: [react()],
  resolve: {
    alias: {
      "@station": here("./framework/ui/src"),
      "@fw-widgets": here("./framework/nexusui/widgets"),
      "@app": app ?? here("./framework/ui/no-app"),
    },
  },
  build: {
    outDir: app ? path.join(app, "ui_dist") : here("./framework/nexusui/ui_dist"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
  },
  server: {
    fs: { allow: [here("."), ...(app ? [app] : [])] },
    proxy: {
      "/api": engine,
      "/ws": { target: engine.replace(/^http/, "ws"), ws: true },
    },
  },
});
