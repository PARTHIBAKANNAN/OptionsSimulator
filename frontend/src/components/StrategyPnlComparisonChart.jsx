function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

// At-a-glance comparison across every backtested strategy (both indices) -- sorted by total P&L
// so winners and losers are immediately obvious, unlike the per-direction rank tables below it.
export function StrategyPnlComparisonChart({ strategies }) {
  const sorted = [...strategies].sort((a, b) => b.total_pnl - a.total_pnl);
  const maxAbs = Math.max(1, ...sorted.map((s) => Math.abs(s.total_pnl)));

  return (
    <div className="space-y-1.5">
      {sorted.map((s) => {
        const positive = s.total_pnl >= 0;
        const widthPct = (Math.abs(s.total_pnl) / maxAbs) * 100;
        return (
          <div key={s.strategy} className="flex items-center gap-1.5 text-[11px] sm:gap-2 sm:text-xs">
            <div className="w-20 shrink-0 truncate text-faint sm:w-52" title={s.strategy}>
              {s.strategy.replace(/^SENSEX_/, "")}
              <span className="ml-1 hidden text-[9px] uppercase text-faint/70 sm:inline">
                {s.strategy.startsWith("SENSEX_") ? "SENSEX" : "NIFTY"}
              </span>
            </div>
            <div className="relative h-4 min-w-0 flex-1 rounded bg-surface3">
              <div
                className={`h-4 rounded ${positive ? "bg-bull" : "bg-bear"}`}
                style={{ width: `${widthPct}%` }}
              />
            </div>
            <div className={`w-16 shrink-0 text-right font-mono tabular-nums sm:w-24 ${positive ? "text-bull" : "text-bear"}`}>
              {fmtRupee(s.total_pnl)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
