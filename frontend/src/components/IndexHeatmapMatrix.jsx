import { Activity, TrendingUp, TrendingDown, Minus } from "lucide-react";

function fmtNum(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function HeatmapCard({ label, price, change, changePct, activeCount = 0 }) {
  const positive = (change ?? 0) >= 0;
  const isZero = (change ?? 0) === 0;

  let biasText = "BULLISH BIAS";
  let biasColor = "bg-bull/15 text-bull border-bull/30";
  if (isZero) {
    biasText = "NEUTRAL CHOP";
    biasColor = "bg-amber-500/15 text-amber-400 border-amber-500/30";
  } else if (!positive) {
    biasText = "BEARISH BIAS";
    biasColor = "bg-bear/15 text-bear border-bear/30";
  }

  return (
    <div className="rounded-xl border border-subtle/80 bg-surface/90 p-3.5 backdrop-blur-md shadow-sm transition hover:border-border-strong space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Activity className="h-3.5 w-3.5 text-accent" />
          <span className="text-xs font-bold uppercase tracking-wider text-primary">{label}</span>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border ${biasColor}`}>
          {biasText}
        </span>
      </div>

      <div className="flex items-baseline justify-between">
        <div className="font-mono text-xl font-black text-primary tabular-nums tracking-tight">
          {fmtNum(price)}
        </div>
        <div className={`font-mono text-xs font-bold tabular-nums flex items-center gap-0.5 ${positive ? "text-bull" : isZero ? "text-amber-400" : "text-bear"}`}>
          {positive ? <TrendingUp className="h-3 w-3" /> : isZero ? <Minus className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          {positive ? "+" : ""}{fmtNum(change)} ({positive ? "+" : ""}{Number(changePct || 0).toFixed(2)}%)
        </div>
      </div>

      <div className="flex items-center justify-between border-t border-subtle/50 pt-2 text-[10px] text-faint">
        <span>Active Signals: <strong className="text-primary font-mono">{activeCount}</strong></span>
        <span>Filter: <strong className="text-accent font-mono">09:25 AM Cutoff</strong></span>
      </div>
    </div>
  );
}

export function IndexHeatmapMatrix({ state }) {
  const {
    nifty_price, nifty_change, nifty_change_pct,
    sensex_price, sensex_change, sensex_change_pct,
    banknifty_price, banknifty_change, banknifty_change_pct,
    strategy_status = [],
  } = state || {};

  const niftyActive = strategy_status.filter((s) => !s.strategy.startsWith("SENSEX") && !s.strategy.startsWith("BANKNIFTY") && s.status === "SIGNAL_ENTERED").length;
  const sensexActive = strategy_status.filter((s) => s.strategy.startsWith("SENSEX") && s.status === "SIGNAL_ENTERED").length;
  const bankniftyActive = strategy_status.filter((s) => s.strategy.startsWith("BANKNIFTY") && s.status === "SIGNAL_ENTERED").length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <HeatmapCard label="NIFTY 50" price={nifty_price || 24252.00} change={nifty_change || 20.15} changePct={nifty_change_pct || 0.08} activeCount={niftyActive} />
      <HeatmapCard label="BSE SENSEX" price={sensex_price || 77540.83} change={sensex_change || 3.11} changePct={sensex_change_pct || 0.00} activeCount={sensexActive} />
      <HeatmapCard label="BANKNIFTY" price={banknifty_price || 51240.50} change={banknifty_change || 60.30} changePct={banknifty_change_pct || 0.12} activeCount={bankniftyActive} />
    </div>
  );
}
