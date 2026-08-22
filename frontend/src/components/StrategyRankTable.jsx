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
      <div className="overflow-x-auto rounded-xl border border-subtle bg-surface">
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

              return (
                <Fragment key={r.strategy}>
                  <tr className="hover:bg-surface2/40 transition">
                    <td className="py-2.5 px-3 text-faint">{i + 1}</td>
                    <td className="py-2.5 px-3 font-sans font-medium text-primary">
                      <div className="flex items-center gap-1.5">
                        <span>{r.strategy}</span>
                        <span className="rounded bg-bull/15 px-1 py-0.2 text-[9px] font-bold text-bull">
                          ACTIVE
                        </span>
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
                          onClick={() => setActiveSpecStrategy(r.strategy)}
                          title="View Quantitative Strategy Formulas & Specifications"
                          className="flex items-center gap-1 rounded bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 px-2 py-1 text-[11px] font-sans font-bold hover:bg-indigo-500 hover:text-white transition shadow-sm"
                        >
                          <BookOpen className="h-3 w-3" /> Specs
                        </button>
                        <button
                          onClick={() => setActiveModalStrategy(r.strategy)}
                          className="flex items-center gap-1 rounded bg-accent px-2 py-1 text-[11px] font-sans font-medium text-white hover:bg-accent/90 transition shadow-sm"
                        >
                          <BarChart2 className="h-3 w-3" /> Analytics
                        </button>
                        {hasDetails && (
                          <button
                            onClick={() => setExpanded(isOpen ? null : r.strategy)}
                            className="flex items-center gap-0.5 rounded bg-surface3 px-2 py-1 text-[11px] font-sans font-medium text-muted hover:bg-surface4 hover:text-primary transition"
                          >
                            Details
                            <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.15 }}>
                              <ChevronDown className="h-3 w-3" />
                            </motion.span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={10} className="p-0">
                      <AnimatePresence initial={false}>
                        {isOpen && hasDetails && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="p-3 bg-surface2/80 border-b border-subtle">
                              {capitalRequirements[r.strategy] && (
                                <div className="mb-3 grid grid-cols-3 gap-2">
                                  <CapitalTile label="Trade Margin + Buffer" value={fmtRupee(capitalRequirements[r.strategy].avg_trade_risk)} />
                                  <CapitalTile label="Max Historical Drawdown" value={fmtRupee(capitalRequirements[r.strategy].max_historical_drawdown)} valueClass="text-bear" />
                                  <CapitalTile label="Recommended Capital" value={fmtRupee(capitalRequirements[r.strategy].recommended_capital)} valueClass="text-accent" />
                                </div>
                              )}
                              {dailyBreakdown[r.strategy] && <MiniEquityCurve days={dailyBreakdown[r.strategy]} />}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </td>
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
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
