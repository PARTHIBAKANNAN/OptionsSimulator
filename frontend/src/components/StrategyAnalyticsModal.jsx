import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Download, TrendingUp, Calendar, ArrowUpRight, ArrowDownRight, Layers, BarChart3, Filter } from "lucide-react";
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
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(iso);
  }
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "text-muted";
}

function computeDetailedStats(trades) {
  const chrono = [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));

  let cumulative = 0;
  let peak = 0;
  let maxDrawdown = 0;
  const equityCurve = [];
  const byInstrument = {};
  const byDow = { 1: { hit: 0, miss: 0, profit: 0, loss: 0 }, 2: { hit: 0, miss: 0, profit: 0, loss: 0 }, 3: { hit: 0, miss: 0, profit: 0, loss: 0 }, 4: { hit: 0, miss: 0, profit: 0, loss: 0 }, 5: { hit: 0, miss: 0, profit: 0, loss: 0 } };
  const byYear = {};
  const monthlyHeatmap = {}; // { '2025': { 1: 1500, 2: -200... } }

  let wins = 0, losses = 0;
  let grossWin = 0, grossLoss = 0;
  let maxProfit = -Infinity, maxLoss = Infinity;
  let streak = 0, streakSign = 0, maxWinStreak = 0, maxLossStreak = 0;

  for (const t of chrono) {
    const pnl = Number(t.net_pnl ?? t.realized_pnl ?? 0);
    cumulative += pnl;
    peak = Math.max(peak, cumulative);
    maxDrawdown = Math.max(maxDrawdown, peak - cumulative);
    equityCurve.push({ date: t.exit_time, cumulative });

    const inst = (t.symbol || t.contract || "NIFTY").includes("SENSEX") ? "SENSEX" : "NIFTY";
    if (!byInstrument[inst]) byInstrument[inst] = { hit: 0, miss: 0, profit: 0, loss: 0 };
    const isWin = pnl > 0;
    byInstrument[inst][isWin ? "hit" : "miss"] += 1;
    byInstrument[inst][isWin ? "profit" : "loss"] += pnl;

    const exitDate = new Date(t.exit_time);
    const dow = exitDate.getDay();
    if (dow >= 1 && dow <= 5) {
      byDow[dow][isWin ? "hit" : "miss"] += 1;
      byDow[dow][isWin ? "profit" : "loss"] += pnl;
    }

    const year = exitDate.getFullYear();
    const month = exitDate.getMonth() + 1;

    if (!byYear[year]) byYear[year] = { hit: 0, miss: 0, profit: 0, loss: 0 };
    byYear[year][isWin ? "hit" : "miss"] += 1;
    byYear[year][isWin ? "profit" : "loss"] += pnl;

    if (!monthlyHeatmap[year]) monthlyHeatmap[year] = {};
    monthlyHeatmap[year][month] = (monthlyHeatmap[year][month] || 0) + pnl;

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
  const winLossRatio = `${wins}:${losses}`;

  return {
    netPnl: cumulative, count, wins, losses, winRate, winLossRatio,
    avgWin, avgLoss, maxProfit: count && maxProfit !== -Infinity ? maxProfit : 0,
    maxLoss: count && maxLoss !== Infinity ? maxLoss : 0,
    maxDrawdown, equityCurve, byInstrument, byDow, byYear, monthlyHeatmap,
    maxWinStreak, maxLossStreak,
  };
}

function MetricCard({ label, value, subValue, valueClass = "" }) {
  return (
    <div className="rounded-xl border border-subtle bg-surface2/80 p-3.5 backdrop-blur-sm">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className={`mt-1 font-mono text-lg sm:text-xl font-bold tabular-nums ${valueClass}`}>{value}</div>
      {subValue && <div className="mt-0.5 text-[10px] text-faint">{subValue}</div>}
    </div>
  );
}

function EquityCurveChart({ points }) {
  if (!points || points.length < 2) {
    return <div className="flex h-48 items-center justify-center text-xs text-faint">Not enough closed trades yet</div>;
  }
  const width = 1000, height = 220, pad = 12;
  const values = points.map((p) => p.cumulative);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const range = max - min || 1;
  const xStep = (width - pad * 2) / (points.length - 1);
  const toXY = (p, i) => [pad + i * xStep, height - pad - ((p.cumulative - min) / range) * (height - pad * 2)];
  const linePath = points.map((p, i) => toXY(p, i).join(",")).join(" L ");
  const last = values[values.length - 1];
  const positive = last >= 0;
  const areaPath = `M ${pad},${height - pad} L ${linePath} L ${pad + (points.length - 1) * xStep},${height - pad} Z`;
  const zeroY = height - pad - ((0 - min) / range) * (height - pad * 2);

  return (
    <div className="relative overflow-hidden rounded-xl border border-subtle bg-surface2/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-faint">Run Summary &middot; Cumulative Equity Curve</span>
        <span className={`font-mono text-sm font-bold ${pnlClass(last)}`}>{last >= 0 ? "+" : ""}{fmtRupee(last)}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-48 w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="eqGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0.45" />
            <stop offset="100%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        {/* Zero baseline */}
        <line x1={pad} y1={zeroY} x2={width - pad} y2={zeroY} stroke="#ef4444" strokeWidth="1" strokeDasharray="3,3" opacity="0.6" />
        <path d={areaPath} fill="url(#eqGradient)" />
        <path d={`M ${linePath}`} fill="none" stroke={positive ? "#22c55e" : "#ef4444"} strokeWidth="2.5" />
      </svg>
    </div>
  );
}

function DualBarRow({ label, hit, miss, profit, loss }) {
  const totalTrades = (hit || 0) + (miss || 0);
  const hitPct = totalTrades ? ((hit / totalTrades) * 100).toFixed(0) : 0;
  const missPct = totalTrades ? ((miss / totalTrades) * 100).toFixed(0) : 0;

  return (
    <div className="grid grid-cols-12 items-center gap-2 text-xs py-1.5 border-b border-subtle/50 last:border-0">
      <div className="col-span-2 font-medium text-primary text-xs">{label}</div>
      {/* Hit / Miss Ratio Bar */}
      <div className="col-span-5 flex items-center gap-2">
        <div className="flex h-3.5 flex-1 overflow-hidden rounded bg-surface3">
          {hit > 0 && <div className="bg-teal-500 transition-all duration-300" style={{ width: `${hitPct}%` }} title={`Hit: ${hit}`} />}
          {miss > 0 && <div className="bg-amber-500 transition-all duration-300" style={{ width: `${missPct}%` }} title={`Miss: ${miss}`} />}
        </div>
        <div className="w-16 text-right font-mono text-[11px] text-faint tabular-nums">
          <span className="text-teal-400 font-semibold">{hit}</span> / <span className="text-amber-400 font-semibold">{miss}</span>
        </div>
      </div>
      {/* Profit / Loss Amount */}
      <div className="col-span-5 flex items-center justify-end gap-2 text-right">
        <span className="font-mono text-xs font-semibold text-bull tabular-nums">+{fmtRupee(Math.round(profit || 0))}</span>
        <span className="font-mono text-xs font-semibold text-bear tabular-nums">-{fmtRupee(Math.abs(Math.round(loss || 0)))}</span>
      </div>
    </div>
  );
}

function MultiYearCalendarHeatmap({ monthlyHeatmap = {} }) {
  const years = Object.keys(monthlyHeatmap).sort();
  if (years.length === 0) return null;

  return (
    <div className="rounded-xl border border-subtle bg-surface2/60 p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-faint">Monthly Profit / Loss Matrix</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-faint text-[11px]">
              <th className="pb-2 text-left font-semibold">Year</th>
              {MONTH_LABELS.map((m) => (
                <th key={m} className="pb-2 text-center font-normal">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody className="space-y-1">
            {years.map((y) => {
              const months = monthlyHeatmap[y] || {};
              return (
                <tr key={y} className="border-t border-subtle/40">
                  <td className="py-2 font-mono font-bold text-primary">{y}</td>
                  {MONTH_LABELS.map((_, i) => {
                    const val = months[i + 1];
                    const isProfit = val > 0;
                    const isLoss = val < 0;
                    return (
                      <td key={i} className="py-1 px-0.5 text-center">
                        <div
                          className={`h-7 rounded flex items-center justify-center font-mono text-[10px] font-semibold transition ${
                            val == null
                              ? "bg-surface3 text-faint/40"
                              : isProfit
                              ? "bg-bull/25 text-bull border border-bull/30"
                              : "bg-bear/25 text-bear border border-bear/30"
                          }`}
                          title={val != null ? `${MONTH_LABELS[i]} ${y}: ${fmtRupee(val)}` : "No trades"}
                        >
                          {val != null ? (val > 0 ? `+${(val / 1000).toFixed(0)}k` : `${(val / 1000).toFixed(0)}k`) : "—"}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function exportCsv(strategy, trades) {
  const header = ["Case", "T.Id", "Instrument", "Entry Timestamp", "Exit Timestamp", "Profit", "Cumulative Profit"];
  const chrono = [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));
  let cumulative = 0;
  const rows = chrono.map((t, i) => {
    cumulative += Number(t.net_pnl ?? t.realized_pnl ?? 0);
    return [i + 1, t.order_id || `TR-${i + 1}`, t.contract || t.symbol, t.entry_time, t.exit_time, t.net_pnl ?? t.realized_pnl, cumulative.toFixed(2)];
  });
  const csv = [header, ...rows].map((r) => r.map((v) => `"${v ?? ""}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${strategy.replace(/\s+/g, "_")}_orders.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function StrategyAnalyticsModal({ strategy, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    setLoading(true);
    fetchStrategyOrders(strategy)
      .then(setData)
      .catch(() => setData({ closed_trades: [] }))
      .finally(() => setLoading(false));
  }, [strategy]);

  const trades = data?.closed_trades ?? [];
  const stats = useMemo(() => computeDetailedStats(trades), [trades]);

  const chrono = useMemo(() => [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)), [trades]);
  const withCumulative = useMemo(() => {
    let cumulative = 0;
    return chrono.map((t, i) => {
      cumulative += Number(t.net_pnl ?? t.realized_pnl ?? 0);
      return { ...t, caseNo: i + 1, cumulativeProfit: cumulative };
    });
  }, [chrono]);

  const rowsDesc = useMemo(() => [...withCumulative].reverse(), [withCumulative]);
  const pageCount = Math.max(1, Math.ceil(rowsDesc.length / pageSize));
  const pageRows = rowsDesc.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-2 sm:p-4 backdrop-blur-md">
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="flex max-h-[92vh] w-full max-w-6xl flex-col rounded-2xl border border-subtle bg-surface shadow-2xl overflow-hidden"
      >
        {/* Modal Top Bar */}
        <div className="flex items-center justify-between border-b border-subtle px-6 py-4 bg-surface2/50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent border border-accent/20">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-lg text-primary">{strategy}</h3>
                <span className="rounded-full bg-bull/15 px-2.5 py-0.5 text-xs font-semibold text-bull border border-bull/20">
                  Completed
                </span>
                <span className="rounded-full bg-surface3 px-2.5 py-0.5 text-xs font-medium text-faint">
                  Historic 1-Yr
                </span>
              </div>
              <p className="text-xs text-faint mt-0.5">QuantMan Analytics &amp; Backtest Performance Breakdown</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-faint hover:bg-surface3 hover:text-primary transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-sm text-faint animate-pulse">Loading Strategy Analytics…</div>
          ) : (
            <>
              {/* Top 12 QuantMan KPI Tiles */}
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-6">
                <MetricCard label="Total Profit" value={fmtRupee(stats.netPnl)} valueClass={pnlClass(stats.netPnl)} />
                <MetricCard label="Win Rate" value={`${stats.winRate.toFixed(1)}%`} valueClass="text-bull" />
                <MetricCard label="Win Loss Ratio" value={stats.winLossRatio} />
                <MetricCard label="Max Drawdown" value={fmtRupee(stats.maxDrawdown)} valueClass="text-bear" />
                <MetricCard label="Avg Profit" value={fmtRupee(stats.avgWin)} valueClass="text-bull" />
                <MetricCard label="Avg Loss" value={fmtRupee(stats.avgLoss)} valueClass="text-bear" />
                <MetricCard label="Max Profit" value={fmtRupee(stats.maxProfit)} valueClass="text-bull" />
                <MetricCard label="Max Loss" value={fmtRupee(stats.maxLoss)} valueClass="text-bear" />
                <MetricCard label="Win Streak" value={stats.maxWinStreak} valueClass="text-bull" />
                <MetricCard label="Loss Streak" value={stats.maxLossStreak} valueClass="text-bear" />
                <MetricCard label="Total Trades" value={stats.count} />
                <MetricCard label="Risk Per Trade" value="0.25%" />
              </div>

              {/* Equity Curve Chart */}
              <EquityCurveChart points={stats.equityCurve} />

              {/* Transaction Analytics Breakdown (Hit/Miss & Day/Year stats) */}
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {/* Left: Instruments & Trade Type */}
                <div className="rounded-xl border border-subtle bg-surface2/60 p-4 space-y-4">
                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Instruments Breakdown</div>
                    {Object.entries(stats.byInstrument).map(([inst, d]) => (
                      <DualBarRow key={inst} label={inst} hit={d.hit} miss={d.miss} profit={d.profit} loss={d.loss} />
                    ))}
                  </div>

                  <div>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Day Of Week Performance</div>
                    {["Mon", "Tue", "Wed", "Thu", "Fri"].map((dName, idx) => {
                      const d = stats.byDow[idx + 1] || { hit: 0, miss: 0, profit: 0, loss: 0 };
                      return <DualBarRow key={dName} label={dName} hit={d.hit} miss={d.miss} profit={d.profit} loss={d.loss} />;
                    })}
                  </div>
                </div>

                {/* Right: Yearly Breakdown & Multi-Year Calendar Grid */}
                <div className="space-y-4">
                  <div className="rounded-xl border border-subtle bg-surface2/60 p-4">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Yearly Summary</div>
                    {Object.entries(stats.byYear).map(([yr, d]) => (
                      <DualBarRow key={yr} label={yr} hit={d.hit} miss={d.miss} profit={d.profit} loss={d.loss} />
                    ))}
                  </div>

                  <MultiYearCalendarHeatmap monthlyHeatmap={stats.monthlyHeatmap} />
                </div>
              </div>

              {/* Transaction Order Details Table */}
              <div className="rounded-xl border border-subtle bg-surface2/60 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-faint">Transaction Order Details</span>
                    <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs font-bold text-accent">
                      {rowsDesc.length} Transactions
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={pageSize}
                      onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
                      className="rounded-lg border border-subtle bg-surface px-2.5 py-1 text-xs text-primary focus:outline-none"
                    >
                      {PAGE_SIZES.map((s) => <option key={s} value={s}>{s} / page</option>)}
                    </select>
                    <button
                      onClick={() => exportCsv(strategy, trades)}
                      className="flex items-center gap-1.5 rounded-lg border border-subtle bg-surface px-3 py-1 text-xs font-medium text-muted hover:bg-surface3 hover:text-primary transition"
                    >
                      <Download className="h-3.5 w-3.5" /> Download CSV
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-subtle bg-surface">
                  <table className="w-full text-xs">
                    <thead className="bg-surface3 text-faint">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold">Case</th>
                        <th className="px-3 py-2 text-left font-semibold">T.Id</th>
                        <th className="px-3 py-2 text-left font-semibold">Instrument</th>
                        <th className="px-3 py-2 text-left font-semibold">Entry</th>
                        <th className="px-3 py-2 text-left font-semibold">Exit</th>
                        <th className="px-3 py-2 text-right font-semibold">Profit</th>
                        <th className="px-3 py-2 text-right font-semibold">Cumulative Profit</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-subtle font-mono">
                      {pageRows.map((t) => {
                        const pnl = Number(t.net_pnl ?? t.realized_pnl ?? 0);
                        return (
                          <tr key={t.order_id || t.caseNo} className="hover:bg-surface2/50 transition">
                            <td className="px-3 py-2 text-faint">{t.caseNo}</td>
                            <td className="px-3 py-2 text-muted">{t.order_id}</td>
                            <td className="px-3 py-2 font-medium text-primary">{t.contract || t.symbol}</td>
                            <td className="px-3 py-2 text-faint">{fmtDate(t.entry_time)}</td>
                            <td className="px-3 py-2 text-faint">{fmtDate(t.exit_time)}</td>
                            <td className={`px-3 py-2 text-right font-bold tabular-nums ${pnlClass(pnl)}`}>
                              {pnl > 0 ? "+" : ""}{fmtRupee(pnl)}
                            </td>
                            <td className={`px-3 py-2 text-right font-bold tabular-nums ${pnlClass(t.cumulativeProfit)}`}>
                              {t.cumulativeProfit > 0 ? "+" : ""}{fmtRupee(t.cumulativeProfit)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination footer */}
                <div className="mt-3 flex items-center justify-between text-xs text-faint">
                  <div>Page {page + 1} of {pageCount} ({rowsDesc.length} total orders)</div>
                  <div className="flex gap-2">
                    <button
                      disabled={page === 0}
                      onClick={() => setPage((p) => p - 1)}
                      className="rounded border border-subtle px-2.5 py-1 disabled:opacity-40 hover:bg-surface3 transition"
                    >
                      Prev
                    </button>
                    <button
                      disabled={page >= pageCount - 1}
                      onClick={() => setPage((p) => p + 1)}
                      className="rounded border border-subtle px-2.5 py-1 disabled:opacity-40 hover:bg-surface3 transition"
                    >
                      Next
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}
