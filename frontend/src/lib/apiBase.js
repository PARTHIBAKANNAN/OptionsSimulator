// import.meta.env.BASE_URL is "/options-simulator/" in the production build (see vite.config.js's
// base, applied only for `build`) and "/" in dev. Prefixing every request with this keeps them
// correctly scoped to this app's own backend regardless of where it's actually being served from
// — without it, an absolute path like fetch("/api/...") resolves from the domain root, which on
// the shared VM gets routed by Caddy to TradeDashBoard's backend instead of this one.
export const API_BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
export const WS_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}${API_BASE}`
    : "";
