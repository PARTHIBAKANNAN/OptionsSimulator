// Trade history isn't streamed — polled every 5s, same as TradeDashBoard's usePaperTradingSync.
// Signal approve/reject are one-off mutations; their effect (position opened, signal resolved)
// flows back to every client through the WS delta, not through this poll.
import { useEffect, useSyncExternalStore } from "react";
import { getSnapshot, setError, setTrades, subscribe } from "../store/tradingStore";
import { API_BASE } from "../lib/apiBase";

const POLL_INTERVAL_MS = 5000;

async function api(path, opts) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", ...opts });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function fetchTradeHistory() {
  try {
    const trades = await api("/api/paper/trades/history");
    setTrades(trades);
  } catch (err) {
    setError(err.message);
  }
}

export function usePaperTradingSync() {
  useEffect(() => {
    fetchTradeHistory();
    const interval = setInterval(fetchTradeHistory, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);
}

export function useTradeHistory() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

export async function approveSignal(signalId) {
  await api(`/api/paper/signals/${signalId}/approve`, { method: "POST" });
}

export async function rejectSignal(signalId) {
  await api(`/api/paper/signals/${signalId}/reject`, { method: "POST" });
}

export async function fetchBacktestReport() {
  return api("/api/backtest/report");
}

export async function fetchStrategyOrders(name) {
  return api(`/api/paper/strategies/${encodeURIComponent(name)}/orders`);
}

export async function fetchPnlReport(params) {
  const qs = new URLSearchParams(params).toString();
  return api(`/api/paper/pnl/report?${qs}`);
}

export async function downloadPnlExport(params) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/api/paper/pnl/export?${qs}`, { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "pnl_export.xlsx";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export { api };
