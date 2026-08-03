import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base matches the Caddy path prefix this app is served under in production
// (see deploy/Caddy-snippet.conf) — /options-simulator/*, sharing the VM/domain
// TradeDashBoard already owns at the root path. Only applied for `build`: in dev,
// serving under a base path too would require prefixing every fetch()/WS URL in
// app code identically to prod, for no benefit — dev proxies straight to :8001 at "/".
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/options-simulator/" : "/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8001",
      "/ws": { target: "ws://127.0.0.1:8001", ws: true },
    },
  },
}));
