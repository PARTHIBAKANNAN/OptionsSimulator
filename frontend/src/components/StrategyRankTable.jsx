import { Fragment, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Badge } from "./ui/Badge";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function MiniEquityCurve({ days }) {
  if (!days || days.length < 2) {
    return <div className="flex h-32 items-center justify-center text-xs text-faint">Not enough days for a curve</div>;
  }
  const width = 800, height = 130, pad = 8;
  const values = days.map((d) => d.cumulative_pnl);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const range = max - min || 1;
  const xStep = (width - pad * 2) / (values.length - 1);
  const toXY = (v, i) => [pad + i * xStep, height - pad - ((v - min) / range) * (height - pad * 2)];
  const linePath = values.map((v, i) => toXY(v, i).join(",")).join(" L ");
  const positive = values[values.length - 1] >= 0;
  const areaPath = `M ${pad},${height - pad} L ${linePath} L ${pad + (values.length - 1) * xStep},${height - pad} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-32 w-full" preserveAspectRatio="none">
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

export function StrategyRankTable({ title, rows, topN = 3, dailyBreakdown = {}, capitalRequirements = {} }) {
  const [expanded, setExpanded] = useState(null);
  const ranked = [...rows].sort((a, b) => (b.profit_factor - a.profit_factor) || (b.win_rate - a.win_rate));

  return (
    <div>
      {title && <div className="mb-2 text-sm font-medium text-muted">{title}</div>}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-faint">
            <th className="pb-1 font-normal">#</th>
            <th className="pb-1 font-normal">Strategy</th>
            <th className="pb-1 font-normal">Trades</th>
            <th className="pb-1 font-normal">Win%</th>
            <th className="pb-1 font-normal">PF</th>
            <th className="pb-1 font-normal">P&amp;L</th>
            <th className="pb-1 font-normal">DD%</th>
            <th className="pb-1 font-normal">Status</th>
            <th className="pb-1 font-normal"></th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((r, i) => {
            const isOpen = expanded === r.strategy;
            const hasDetails = Boolean(dailyBreakdown[r.strategy] || capitalRequirements[r.strategy]);
            return (
              <Fragment key={r.strategy}>
                <tr className="border-t border-subtle">
                  <td className="py-1.5">{i + 1}</td>
                  <td className="py-1.5 font-medium">{r.strategy}</td>
                  <td className="py-1.5">{r.total_trades}</td>
                  <td className="py-1.5">{r.win_rate}%</td>
                  <td className="py-1.5">{r.profit_factor}</td>
                  <td className={`py-1.5 ${r.total_pnl >= 0 ? "text-bull" : "text-bear"}`}>
                    {fmtRupee(r.total_pnl)}
                  </td>
                  <td className="py-1.5">{r.max_drawdown_pct}%</td>
                  <td className="py-1.5">
                    {i < topN && r.total_trades > 0 ? <Badge variant="accent">DEPLOY</Badge> : <span className="text-faint">—</span>}
                  </td>
                  <td className="py-1.5 text-right">
                    {hasDetails && (
                      <button
                        onClick={() => setExpanded(isOpen ? null : r.strategy)}
                        className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-muted hover:bg-surface3 hover:text-primary"
                      >
                        Details
                        <motion.span animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.15 }}>
                          <ChevronDown className="h-3.5 w-3.5" />
                        </motion.span>
                      </button>
                    )}
                  </td>
                </tr>
                <tr>
                  <td colSpan={9} className="p-0">
                    <AnimatePresence initial={false}>
                      {isOpen && hasDetails && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="mb-3 rounded-lg border border-subtle bg-surface2 p-3">
                            {capitalRequirements[r.strategy] && (
                              <div className="mb-3 grid grid-cols-3 gap-2">
                                <CapitalTile label="Avg Trade Risk" value={fmtRupee(capitalRequirements[r.strategy].avg_trade_risk)} />
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
  );
}
