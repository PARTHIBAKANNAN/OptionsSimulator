import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Download } from "lucide-react";
import { Badge } from "./ui/Badge";
import { fetchStrategyOrders } from "../hooks/usePaperTradingSync";

const DOW_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const PAGE_SIZES = [10, 25, 50];

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "text-muted";
}

function instrumentOf(contract) {
  if (!contract) return "—";
  const trimmed = contract.trim();
  return trimmed.endsWith("CE") ? "CE" : trimmed.endsWith("PE") ? "PE" : "OTHER";
}

// All strategy-level analytics are derived client-side from the existing /orders endpoint's
// closed_trades -- no new backend route needed for a first, fully-functional version of this view.
function computeStats(trades) {
  const chrono = [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));

  let cumulative = 0;
  let peak = 0;
  let maxDrawdown = 0;
  const equityCurve = [];
  const byInstrument = {};
  const byDow = DOW_LABELS.map(() => ({ hit: 0, miss: 0, profit: 0, loss: 0 }));
  const byMonth = {};

  let wins = 0, losses = 0;
  let grossWin = 0, grossLoss = 0;
  let maxProfit = -Infinity, maxLoss = Infinity;
  let streak = 0, streakSign = 0, maxWinStreak = 0, maxLossStreak = 0;

  for (const t of chrono) {
    const pnl = t.net_pnl ?? 0;
    cumulative += pnl;
    peak = Math.max(peak, cumulative);
    maxDrawdown = Math.max(maxDrawdown, peak - cumulative);
    equityCurve.push({ date: t.exit_time, cumulative });

    const inst = instrumentOf(t.contract);
    if (!byInstrument[inst]) byInstrument[inst] = { hit: 0, miss: 0, profit: 0, loss: 0 };
    const isWin = pnl > 0;
    byInstrument[inst][isWin ? "hit" : "miss"] += 1;
    byInstrument[inst][isWin ? "profit" : "loss"] += pnl;

    const dow = new Date(t.exit_time).getDay();
    byDow[dow][isWin ? "hit" : "miss"] += 1;
    byDow[dow][isWin ? "profit" : "loss"] += pnl;

    const d = new Date(t.exit_time);
    const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    byMonth[monthKey] = (byMonth[monthKey] || 0) + pnl;

    if (isWin) {
      wins += 1; grossWin += pnl; maxProfit = Math.max(maxProfit, pnl);
      streak = streakSign === 1 ? streak + 1 : 1; streakSign = 1;
      maxWinStreak = Math.max(maxWinStreak, streak);
    } else {
      losses += 1; grossLoss += pnl; maxLoss = Math.min(maxLoss, pnl);
      streak = streakSign === -1 ? streak + 1 : 1; streakSign = -1;
      maxLossStreak = Math.max(maxLossStreak, streak);
    }
  }

  const count = chrono.length;
  const winRate = count ? (wins / count) * 100 : 0;
  const avgWin = wins ? grossWin / wins : 0;
  const avgLoss = losses ? grossLoss / losses : 0;
  const winLossRatio = losses && avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : wins ? Infinity : 0;

  return {
    netPnl: cumulative, count, wins, losses, winRate, winLossRatio,
    avgWin, avgLoss, maxProfit: count ? maxProfit : 0, maxLoss: count ? maxLoss : 0,
    maxDrawdown, equityCurve, byInstrument, byDow, byMonth,
    currentStreak: streak * streakSign, maxWinStreak, maxLossStreak,
  };
}

function MetricCard({ label, value, valueClass = "" }) {
  return (
    <div className="rounded-lg border border-subtle bg-surface2 p-4">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className={`mt-1 font-mono text-xl font-bold tabular-nums ${valueClass}`}>{value}</div>
    </div>
  );
}

function EquityCurve({ points }) {
  if (points.length < 2) {
    return <div className="flex h-40 items-center justify-center text-sm text-faint">Not enough closed trades yet</div>;
  }
  const width = 800, height = 160, pad = 8;
  const values = points.map((p) => p.cumulative);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const range = max - min || 1;
  const xStep = (width - pad * 2) / (points.length - 1);
  const toXY = (p, i) => [pad + i * xStep, height - pad - ((p.cumulative - min) / range) * (height - pad * 2)];
  const linePath = points.map((p, i) => toXY(p, i).join(",")).join(" L ");
  const last = values[values.length - 1];
  const positive = last >= 0;
  const areaPath = `M ${pad},${height - pad} L ${linePath} L ${pad + (points.length - 1) * xStep},${height - pad} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0.35" />
          <stop offset="100%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#equityFill)" />
      <path d={`M ${linePath}`} fill="none" stroke={positive ? "#22c55e" : "#ef4444"} strokeWidth="2" />
    </svg>
  );
}

function HitMissBars({ title, buckets, labels }) {
  const maxCount = Math.max(1, ...Object.values(buckets).flatMap((b) => [b.hit, b.miss]));
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">{title}</div>
      <div className="space-y-2">
        {labels.map((label, i) => {
          const key = typeof label === "string" && buckets[label] ? label : i;
          const b = buckets[key] ?? { hit: 0, miss: 0 };
          return (
            <div key={label} className="flex items-center gap-2 text-xs">
              <div className="w-10 shrink-0 text-faint">{label}</div>
              <div className="flex h-3 flex-1 overflow-hidden rounded bg-surface3">
                <div className="bg-hit" style={{ width: `${(b.hit / maxCount) * 100}%` }} />
                <div className="bg-warn" style={{ width: `${(b.miss / maxCount) * 100}%` }} />
              </div>
              <div className="w-16 shrink-0 text-right font-mono tabular-nums text-faint">{b.hit}/{b.miss}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProfitLossBars({ title, buckets, labels }) {
  const maxAbs = Math.max(1, ...Object.values(buckets).flatMap((b) => [Math.abs(b.profit), Math.abs(b.loss)]));
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">{title}</div>
      <div className="space-y-2">
        {labels.map((label, i) => {
          const key = typeof label === "string" && buckets[label] ? label : i;
          const b = buckets[key] ?? { profit: 0, loss: 0 };
          return (
            <div key={label} className="flex items-center gap-2 text-xs">
              <div className="w-10 shrink-0 text-faint">{label}</div>
              <div className="flex h-3 flex-1 overflow-hidden rounded bg-surface3">
                <div className="bg-bull" style={{ width: `${(b.profit / maxAbs) * 100}%` }} />
                <div className="bg-bear" style={{ width: `${(Math.abs(b.loss) / maxAbs) * 100}%` }} />
              </div>
              <div className="w-20 shrink-0 text-right font-mono tabular-nums text-faint">
                {fmtRupee(Math.round(b.profit + b.loss))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalendarHeatmap({ byMonth }) {
  const year = new Date().getFullYear();
  const values = MONTH_LABELS.map((_, i) => byMonth[`${year}-${String(i + 1).padStart(2, "0")}`] ?? null);
  const maxAbs = Math.max(1, ...values.filter((v) => v != null).map(Math.abs));

  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">P&amp;L Calendar &middot; {year}</div>
      <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-6 lg:grid-cols-12">
        {MONTH_LABELS.map((label, i) => {
          const v = values[i];
          const intensity = v == null ? 0 : Math.min(1, Math.abs(v) / maxAbs);
          const bg = v == null
            ? "bg-surface3"
            : v > 0 ? `rgba(34,197,94,${0.15 + intensity * 0.65})` : `rgba(239,68,68,${0.15 + intensity * 0.65})`;
          return (
            <div
              key={label}
              className="min-w-0 rounded p-1.5 text-center text-[10px] sm:p-2"
              style={{ background: v == null ? undefined : bg }}
              title={v == null ? `${label}: no trades` : `${label}: ${fmtRupee(Math.round(v))}`}
            >
              <div className={v == null ? "text-faint" : "font-medium text-primary"}>{label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function exportCsv(strategy, trades) {
  const header = ["Case", "T.Id", "Instrument", "Entry Timestamp", "Exit Timestamp", "Profit", "Cumulative Profit"];
  const chrono = [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));
  let cumulative = 0;
  const rows = chrono.map((t, i) => {
    cumulative += t.net_pnl ?? 0;
    return [i + 1, t.order_id, t.contract, t.entry_time, t.exit_time, t.net_pnl, cumulative.toFixed(2)];
  });
  const csv = [header, ...rows].map((r) => r.map((v) => `"${v ?? ""}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${strategy.replace(/\s+/g, "_")}_transactions.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function TransactionTable({ strategy, trades }) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const chrono = useMemo(() => [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)), [trades]);
  const withCumulative = useMemo(() => {
    let cumulative = 0;
    return chrono.map((t, i) => {
      cumulative += t.net_pnl ?? 0;
      return { ...t, caseNo: i + 1, cumulativeProfit: cumulative };
    });
  }, [chrono]);
  const rowsDesc = useMemo(() => [...withCumulative].reverse(), [withCumulative]);
  const pageCount = Math.max(1, Math.ceil(rowsDesc.length / pageSize));
  const pageRows = rowsDesc.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-faint">Transaction Order Details</div>
        <div className="flex items-center gap-2">
          <select
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
            className="rounded border border-subtle bg-surface2 px-2 py-1 text-xs"
          >
            {PAGE_SIZES.map((s) => <option key={s} value={s}>{s}/page</option>)}
          </select>
          <button
            onClick={() => exportCsv(strategy, trades)}
            className="flex items-center gap-1 rounded border border-subtle px-2 py-1 text-xs font-medium text-muted hover:bg-surface3 hover:text-primary"
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-subtle">
        <table className="w-full text-xs">
          <thead className="bg-surface2 text-faint">
            <tr>
              {["Case", "Instrument", "Entry", "Exit", "Profit", "Cumulative Profit"].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-semibold uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-4 text-center text-faint">No closed trades yet</td></tr>
            )}
            {pageRows.map((t) => (
              <tr key={t.order_id} className="border-t border-subtle">
                <td className="px-3 py-2 text-faint">{t.caseNo}</td>
                <td className="px-3 py-2 font-mono">{t.contract}</td>
                <td className="px-3 py-2 text-faint">{fmtDate(t.entry_time)}</td>
                <td className="px-3 py-2 text-faint">{fmtDate(t.exit_time)}</td>
                <td className={`px-3 py-2 font-mono font-medium tabular-nums ${pnlClass(t.net_pnl)}`}>{fmtRupee(t.net_pnl)}</td>
                <td className={`px-3 py-2 font-mono tabular-nums ${pnlClass(t.cumulativeProfit)}`}>{fmtRupee(t.cumulativeProfit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="mt-2 flex items-center justify-end gap-2 text-xs text-faint">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
            className="rounded border border-subtle px-2 py-1 disabled:opacity-40"
          >Prev</button>
          <span>Page {page + 1} of {pageCount}</span>
          <button
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))} disabled={page >= pageCount - 1}
            className="rounded border border-subtle px-2 py-1 disabled:opacity-40"
          >Next</button>
        </div>
      )}
    </div>
  );
}

export function StrategyAnalyticsModal({ strategy, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchStrategyOrders(strategy)
      .then((r) => { if (!cancelled) setData(r); })
      .catch((e) => { if (!cancelled) setError(e.message || "Failed to load"); });
    return () => { cancelled = true; };
  }, [strategy]);

  const stats = useMemo(() => (data ? computeStats(data.closed_trades) : null), [data]);
  const isLive = Boolean(data?.current_signal?.entry);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-0 backdrop-blur-sm sm:p-4"
        onClick={onClose}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}
      >
        <motion.div
          className="flex h-full w-full max-w-6xl flex-col rounded-none border-0 border-subtle bg-surface shadow-2xl sm:h-auto sm:max-h-[90vh] sm:rounded-xl sm:border"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.97, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 12 }} transition={{ duration: 0.18, ease: "easeOut" }}
        >
          <div className="flex items-center justify-between border-b border-subtle px-3 py-3 sm:px-5">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold">{strategy}</h2>
              <Badge variant="accent">Paper</Badge>
              <Badge variant={isLive ? "bull" : "neutral"}>{isLive ? "Signal Entered" : "Idle"}</Badge>
            </div>
            <button onClick={onClose} className="rounded p-1 text-faint hover:bg-surface3 hover:text-primary">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-3 sm:px-5 sm:py-4">
            {error && <div className="py-8 text-center text-sm text-bear">{error}</div>}
            {!error && !stats && <div className="py-8 text-center text-sm text-faint">Loading…</div>}

            {stats && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MetricCard label="Net P&L" value={fmtRupee(Math.round(stats.netPnl))} valueClass={pnlClass(stats.netPnl)} />
                  <MetricCard label="Run Type" value="Live / Paper" />
                  <MetricCard label="Order Type" value="Forward Testing" />
                  <MetricCard
                    label="Wallet Balance"
                    value={data.wallet ? fmtRupee(data.wallet.balance) : "—"}
                    valueClass={data.wallet ? pnlClass(data.wallet.pnl_in_wallet) : ""}
                  />
                </div>

                <div className="rounded-lg border border-subtle bg-surface2 p-4">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Equity Curve</div>
                  <EquityCurve points={stats.equityCurve} />
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MetricCard label="Winning Probability" value={`${stats.winRate.toFixed(1)}%`} />
                  <MetricCard label="Win/Loss Ratio" value={Number.isFinite(stats.winLossRatio) ? stats.winLossRatio.toFixed(2) : "∞"} />
                  <MetricCard label="Max Drawdown" value={fmtRupee(Math.round(stats.maxDrawdown))} valueClass="text-bear" />
                  <MetricCard
                    label="Win/Loss Streak"
                    value={`${stats.currentStreak >= 0 ? "+" : ""}${stats.currentStreak}`}
                    valueClass={pnlClass(stats.currentStreak)}
                  />
                  <MetricCard label="Avg Profit" value={fmtRupee(Math.round(stats.avgWin))} valueClass="text-bull" />
                  <MetricCard label="Avg Loss" value={fmtRupee(Math.round(stats.avgLoss))} valueClass="text-bear" />
                  <MetricCard label="Max Profit" value={fmtRupee(Math.round(stats.maxProfit))} valueClass="text-bull" />
                  <MetricCard label="Max Loss" value={fmtRupee(Math.round(stats.maxLoss))} valueClass="text-bear" />
                </div>

                <div className="rounded-lg border border-subtle bg-surface2 p-4">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-faint">Transactions Analytics</div>
                  <div className="grid gap-6 sm:grid-cols-2">
                    <HitMissBars title="Hit / Miss by Instrument" buckets={stats.byInstrument} labels={Object.keys(stats.byInstrument)} />
                    <HitMissBars title="Hit / Miss by Day of Week" buckets={stats.byDow} labels={DOW_LABELS} />
                    <ProfitLossBars title="Profit / Loss by Instrument" buckets={stats.byInstrument} labels={Object.keys(stats.byInstrument)} />
                    <ProfitLossBars title="Profit / Loss by Day of Week" buckets={stats.byDow} labels={DOW_LABELS} />
                  </div>
                </div>

                <div className="rounded-lg border border-subtle bg-surface2 p-4">
                  <CalendarHeatmap byMonth={stats.byMonth} />
                </div>

                <TransactionTable strategy={strategy} trades={data.closed_trades} />
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
