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

export { api };
