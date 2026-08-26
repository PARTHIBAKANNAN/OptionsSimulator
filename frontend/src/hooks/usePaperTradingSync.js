import { API_BASE } from "../lib/apiBase";

export async function api(path, opts) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", ...opts });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function approveSignal(signalId) {
  await api(`/api/paper/signals/${signalId}/approve`, { method: "POST" });
}

export async function rejectSignal(signalId) {
  await api(`/api/paper/signals/${signalId}/reject`, { method: "POST" });
}

export async function closePosition(orderId) {
  return api(`/api/paper/positions/${orderId}/close`, { method: "POST" });
}

export async function closeAllPositions() {
  return api("/api/paper/positions/close-all", { method: "POST" });
}

export async function restartStrategy(name) {
  return api(`/api/paper/strategies/${encodeURIComponent(name)}/restart`, { method: "POST" });
}

export async function fetchBacktestReport() {
  return api("/api/backtest/report");
}

export async function fetchBacktestDailyBreakdown() {
  return api("/api/backtest/daily-breakdown");
}

export async function fetchBacktestCapitalRequirements() {
  return api("/api/backtest/capital-requirements");
}

export async function fetchStrategyOrders(name) {
  return api(`/api/paper/strategies/${encodeURIComponent(name)}/orders`);
}

export async function fetchBacktestStrategyHistory(name) {
  try {
    return await api(`/api/backtest/strategies/${encodeURIComponent(name)}/history`);
  } catch {
    return await api(`/api/paper/strategies/${encodeURIComponent(name)}/history`);
  }
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
