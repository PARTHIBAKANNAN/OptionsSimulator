import { Fragment, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, BarChart2, BookOpen } from "lucide-react";
import { Badge } from "./ui/Badge";
import { StrategyAnalyticsModal } from "./StrategyAnalyticsModal";
import { StrategyDetailModal } from "./StrategyDetailModal";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function MiniEquityCurve({ days }) {
  if (!days || days.length < 2) {
    return <div className="flex h-28 items-center justify-center text-xs text-faint">Not enough days for a curve</div>;
  }
  const width = 800, height = 110, pad = 8;
  const values = days.map((d) => d.cumulative_pnl);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const range = max - min || 1;
  const xStep = (width - pad * 2) / (values.length - 1);
  const toXY = (v, i) => [pad + i * xStep, height - pad - ((v - min) / range) * (height - pad * 2)];
  const linePath = values.map((v, i) => toXY(v, i).join(",")).join(" L ");
  const positive = values[values.length - 1] >= 0;
  const areaPath = `M ${pad},${height - pad} L ${linePath} L ${pad + (values.length - 1) * xStep},${height - pad} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-28 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="rankEquityFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0.35" />
          <stop offset="100%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#rankEquityFill)" />
      <path d={`M ${linePath}`} fill="none" stroke={positive ? "#22c55e" : "#ef4444"} strokeWidth="2" />
    </svg>
  );
}

function CapitalTile({ label, value, valueClass = "" }) {
  return (
    <div className="rounded-lg border border-subtle bg-surface2 px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className={`font-mono text-sm font-bold tabular-nums ${valueClass}`}>{value}</div>
    </div>
  );
}

export function StrategyRankTable({ title, rows, dailyBreakdown = {}, capitalRequirements = {} }) {
  const [expanded, setExpanded] = useState(null);
  const [activeModalStrategy, setActiveModalStrategy] = useState(null);
  const [activeSpecStrategy, setActiveSpecStrategy] = useState(null);
  const ranked = [...rows].sort((a, b) => (b.profit_factor - a.profit_factor) || (b.total_pnl - a.total_pnl));

  return (
    <div>
      {title && <div className="mb-2 text-sm font-medium text-muted">{title}</div>}
      <div className="hidden md:block overflow-x-auto rounded-xl border border-subtle bg-surface">
        <table className="w-full min-w-[720px] text-xs">
          <thead>
            <tr className="bg-surface2/60 text-left text-faint text-[11px]">
              <th className="py-2.5 px-3 font-semibold uppercase">#</th>
              <th className="py-2.5 px-3 font-semibold uppercase">Strategy</th>
              <th className="py-2.5 px-3 font-semibold uppercase">TF</th>
              <th className="py-2.5 px-3 font-semibold uppercase">Strike</th>
              <th className="py-2.5 px-3 font-semibold uppercase">Trades</th>
              <th className="py-2.5 px-3 font-semibold uppercase">Win%</th>
              <th className="py-2.5 px-3 font-semibold uppercase">PF</th>
              <th className="py-2.5 px-3 font-semibold uppercase">Total P&amp;L</th>
              <th className="py-2.5 px-3 font-semibold uppercase">Max DD%</th>
              <th className="py-2.5 px-3 font-semibold uppercase text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-subtle font-mono">
            {ranked.map((r, i) => {
              const isOpen = expanded === r.strategy;
              const hasDetails = Boolean(dailyBreakdown[r.strategy] || capitalRequirements[r.strategy]);
              const is5M = r.strategy.includes("_5M_");
              const isITM = r.strategy.includes("_ITM");

              const isTop3 = i < 3;
              const alphaBadge = i === 0 ? "🏆 Alpha 1" : i === 1 ? "🥈 Alpha 2" : i === 2 ? "🥉 Alpha 3" : null;
              const isLaggard = r.total_pnl < 0;

              return (
                <Fragment key={r.strategy}>
                  <tr className={`transition ${isTop3 ? "bg-amber-500/[0.04] hover:bg-amber-500/[0.08]" : "hover:bg-surface2/40"}`}>
                    <td className="py-2.5 px-3">
                      <span className={`font-bold ${isTop3 ? "text-amber-400" : "text-faint"}`}>{i + 1}</span>
                    </td>
                    <td className="py-2.5 px-3 font-sans font-medium text-primary">
                      <div className="flex items-center gap-1.5">
                        <span className={isTop3 ? "font-bold text-primary" : ""}>{r.strategy}</span>
                        {alphaBadge ? (
                          <span className="rounded bg-amber-500/20 border border-amber-500/40 px-1.5 py-0.5 text-[9px] font-bold text-amber-400">
                            {alphaBadge}
                          </span>
                        ) : isLaggard ? (
                          <span className="rounded bg-bear/15 border border-bear/30 px-1 py-0.2 text-[9px] font-bold text-bear">
                            LAGGARD
                          </span>
                        ) : (
                          <span className="rounded bg-bull/15 px-1 py-0.2 text-[9px] font-bold text-bull">
                            ACTIVE
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${is5M ? "bg-amber-500/15 text-amber-400" : "bg-surface3 text-faint"}`}>
                        {is5M ? "5M" : "1M"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${isITM ? "bg-emerald-500/15 text-emerald-400" : "bg-blue-500/15 text-blue-400"}`}>
                        {isITM ? "ITM" : "ATM"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">{r.total_trades}</td>
                    <td className="py-2.5 px-3 text-bull font-bold">{r.win_rate}%</td>
                    <td className="py-2.5 px-3 font-semibold">{r.profit_factor >= 900 ? "inf" : r.profit_factor}</td>
                    <td className={`py-2.5 px-3 font-bold tabular-nums ${r.total_pnl >= 0 ? "text-bull" : "text-bear"}`}>
                      {r.total_pnl >= 0 ? "+" : ""}{fmtRupee(r.total_pnl)}
                    </td>
                    <td className="py-2.5 px-3 text-faint">{r.max_drawdown_pct}%</td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setActiveSpecStrategy({
                            ...r,
                            capital: capitalRequirements[r.strategy],
                            daily: dailyBreakdown[r.strategy],
                          })}
                          title="View Strategy Overview & Capital Requirements"
                          className="flex items-center gap-1 rounded bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 px-2.5 py-1 text-[11px] font-sans font-bold hover:bg-indigo-500 hover:text-white transition shadow-sm"
                        >
                          <BookOpen className="h-3 w-3" /> Specs &amp; Details
                        </button>
                        <button
                          onClick={() => setActiveModalStrategy(r.strategy)}
                          className="flex items-center gap-1 rounded bg-accent px-2.5 py-1 text-[11px] font-sans font-medium text-white hover:bg-accent/90 transition shadow-sm"
                        >
                          <BarChart2 className="h-3 w-3" /> Analytics
                        </button>
                      </div>
                    </td>
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile Ranked Cards (Zero Horizontal Scroll) */}
      <div className="block md:hidden space-y-2.5">
        {ranked.map((r, i) => {
          const is5M = r.strategy.includes("_5M_");
          const isITM = r.strategy.includes("_ITM");
          const isTop3 = i < 3;
          const alphaBadge = i === 0 ? "🏆 Alpha 1" : i === 1 ? "🥈 Alpha 2" : i === 2 ? "🥉 Alpha 3" : null;

          return (
            <div
              key={r.strategy}
              className={`rounded-xl border border-subtle bg-surface p-3.5 space-y-2.5 shadow-sm ${
                isTop3 ? "border-amber-500/30 bg-amber-500/[0.02]" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded ${isTop3 ? "bg-amber-500/20 text-amber-400" : "bg-surface3 text-faint"}`}>
                      #{i + 1}
                    </span>
                    <span className="font-sans font-bold text-xs text-primary truncate max-w-[210px]" title={r.strategy}>
                      {r.strategy}
                    </span>
                    {alphaBadge && (
                      <span className="rounded bg-amber-500/20 border border-amber-500/40 px-1.5 py-0.2 text-[9px] font-bold text-amber-400">
                        {alphaBadge}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 text-[10px] text-faint mt-1">
                    <span className={`px-1.5 py-0.2 rounded font-bold ${is5M ? "bg-amber-500/15 text-amber-400" : "bg-surface3 text-faint"}`}>
                      {is5M ? "5M" : "1M"}
                    </span>
                    <span className={`px-1.5 py-0.2 rounded font-bold ${isITM ? "bg-indigo-500/15 text-indigo-400" : "bg-surface3 text-faint"}`}>
                      {isITM ? "ITM" : "ATM"}
                    </span>
                    <span>· DD: {r.max_drawdown_pct}%</span>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <div className={`font-mono text-sm font-extrabold tabular-nums ${r.total_pnl >= 0 ? "text-bull" : "text-bear"}`}>
                    {r.total_pnl >= 0 ? "+" : ""}{fmtRupee(r.total_pnl)}
                  </div>
                  <div className="text-[10px] text-faint font-mono">
                    PF: {r.profit_factor >= 900 ? "inf" : r.profit_factor}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 rounded-lg bg-surface2/60 p-2 text-center text-[11px] font-mono border border-subtle/40">
                <div>
                  <div className="text-[9px] uppercase font-sans font-semibold text-faint">Trades</div>
                  <div className="font-bold text-primary">{r.total_trades}</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase font-sans font-semibold text-faint">Win Rate</div>
                  <div className="font-bold text-bull">{r.win_rate}%</div>
                </div>
                <div>
                  <div className="text-[9px] uppercase font-sans font-semibold text-faint">Max DD</div>
                  <div className="text-faint">{r.max_drawdown_pct}%</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-0.5">
                <button
                  onClick={() => setActiveSpecStrategy({
                    ...r,
                    capital: capitalRequirements[r.strategy],
                    daily: dailyBreakdown[r.strategy],
                  })}
                  className="rounded-lg bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 py-1.5 text-xs font-bold hover:bg-indigo-500 hover:text-white transition flex items-center justify-center gap-1 active:scale-95"
                >
                  <BookOpen className="h-3.5 w-3.5" /> Specs
                </button>
                <button
                  onClick={() => setActiveModalStrategy(r.strategy)}
                  className="rounded-lg bg-accent text-white py-1.5 text-xs font-bold hover:bg-accent/90 transition flex items-center justify-center gap-1 shadow-sm active:scale-95"
                >
                  <BarChart2 className="h-3.5 w-3.5" /> Analytics
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {activeModalStrategy && (
        <StrategyAnalyticsModal strategy={activeModalStrategy} mode="backtest" onClose={() => setActiveModalStrategy(null)} />
      )}

      {activeSpecStrategy && (
        <StrategyDetailModal strategy={activeSpecStrategy} onClose={() => setActiveSpecStrategy(null)} />
      )}
    </div>
  );
}
