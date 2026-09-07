import { useEffect, useState, useMemo, useRef } from "react";
import { 
  TrendingUp, 
  TrendingDown, 
  Zap, 
  ShieldCheck, 
  Wallet, 
  Award, 
  AlertTriangle, 
  Layers, 
  BarChart3, 
  Activity,
  Flame
} from "lucide-react";
import { fetchLiveAnalyticsOverview } from "../hooks/usePaperTradingSync";
import { useMarketState } from "../hooks/useMarketStream";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "text-muted";
}

function LivePortfolioGrowthSvgChart({ data }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(600);
  const HEIGHT = 240;
  const PADDING = 15;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) setWidth(entries[0].contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (!data || data.length < 2) {
    return (
      <div ref={containerRef} className="flex h-56 items-center justify-center text-xs text-faint font-mono">
        Not enough historical live sessions recorded yet to chart multi-day progression.
      </div>
    );
  }

  const points = data.map((d) => d.cumulative_pnl);
  const min = Math.min(0, ...points);
  const max = Math.max(0, ...points);
  const range = max - min || 1;
  const scaleX = (i) => PADDING + (i / (points.length - 1)) * (width - 2 * PADDING);
  const scaleY = (v) => HEIGHT - PADDING - ((v - min) / range) * (HEIGHT - 2 * PADDING);
  const linePath = points.map((v, i) => `${scaleX(i)},${scaleY(v)}`).join(" L ");
  const zeroY = scaleY(0);
  const final = points[points.length - 1];
  const positive = final >= 0;
  const areaPath = `M ${PADDING},${HEIGHT - PADDING} L ${linePath} L ${scaleX(points.length - 1)},${HEIGHT - PADDING} Z`;

  return (
    <div ref={containerRef} className="w-full">
      <svg width={width} height={HEIGHT} className="overflow-visible">
        <defs>
          <linearGradient id="growthFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={positive ? "#10b981" : "#f43f5e"} stopOpacity="0.4" />
            <stop offset="100%" stopColor={positive ? "#10b981" : "#f43f5e"} stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <line x1={0} y1={zeroY} x2={width} y2={zeroY} stroke="#333333" strokeDasharray="4 4" />
        <path d={areaPath} fill="url(#growthFill)" />
        <path d={`M ${linePath}`} fill="none" stroke={positive ? "#10b981" : "#f43f5e"} strokeWidth={2.5} />
      </svg>
    </div>
  );
}

export function ExecutiveDashboardScreen() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Live streaming market state
  const liveState = useMarketState();

  useEffect(() => {
    fetchLiveAnalyticsOverview()
      .then((data) => {
        setAnalytics(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const openPositions = liveState.positions || [];
  const strategyStatusList = liveState.strategy_status || [];

  // Categorize 44 strategies into NIFTY, BANKNIFTY, SENSEX
  const categorizedStrategies = useMemo(() => {
    const groups = { NIFTY: [], BANKNIFTY: [], SENSEX: [] };
    strategyStatusList.forEach((s) => {
      const name = s.strategy.toUpperCase();
      if (name.startsWith("BANKNIFTY")) {
        groups.BANKNIFTY.push(s);
      } else if (name.startsWith("SENSEX")) {
        groups.SENSEX.push(s);
      } else {
        groups.NIFTY.push(s);
      }
    });
    return groups;
  }, [strategyStatusList]);

  // Live total P&L today
  const todayRealizedPnl = liveState.pnl?.today_realized_pnl || 0;
  const runningPnl = openPositions.reduce((sum, p) => sum + (p.trade_pnl || 0), 0);
  const todayGrossPnl = todayRealizedPnl + runningPnl;

  return (
    <div className="space-y-6">
      {/* 1. Header Banner */}
      <div className="rounded-xl border border-subtle bg-surface p-4 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-accent/20 to-cyan-500/20 text-accent shadow-inner">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg sm:text-xl font-black tracking-tight text-primary">
                  Executive Quant Dashboard
                </h1>
                <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-400 border border-emerald-500/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                  LIVE TELEMETRY
                </span>
              </div>
              <p className="text-xs text-faint mt-0.5">
                Multi-Index Execution Engine · 44 Systematic Strategies · Fyers Live Broker Feed
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <div className="rounded-lg bg-surface2 px-3 py-2 border border-subtle">
              <span className="text-faint block text-[10px] uppercase font-semibold">Live Mode</span>
              <span className="font-bold text-accent">Auto-Execution Active</span>
            </div>
            <div className="rounded-lg bg-surface2 px-3 py-2 border border-subtle">
              <span className="text-faint block text-[10px] uppercase font-semibold">Active Trades</span>
              <span className="font-bold text-primary">{openPositions.length} Open</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Institutional KPI Hero Bar (Live + All-Time) */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-xl border border-subtle bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between text-faint">
            <span className="text-[11px] font-bold uppercase tracking-wider">All-Time Net P&L</span>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div className={`mt-2 font-mono text-lg sm:text-xl font-extrabold tabular-nums ${pnlClass(analytics?.all_time_net_pnl || 0)}`}>
            {fmt(analytics?.all_time_net_pnl || 0)}
          </div>
          <div className="mt-1 text-[10px] text-faint font-sans">
            Realized Live Wallet Capital
          </div>
        </div>

        <div className="rounded-xl border border-subtle bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between text-faint">
            <span className="text-[11px] font-bold uppercase tracking-wider">Today's Alpha</span>
            <Zap className="h-4 w-4 text-accent" />
          </div>
          <div className={`mt-2 font-mono text-lg sm:text-xl font-extrabold tabular-nums ${pnlClass(todayGrossPnl)}`}>
            {fmt(todayGrossPnl)}
          </div>
          <div className="mt-1 text-[10px] text-faint font-sans">
            Realized: {fmt(todayRealizedPnl)}
          </div>
        </div>

        <div className="rounded-xl border border-subtle bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between text-faint">
            <span className="text-[11px] font-bold uppercase tracking-wider">All-Time Win %</span>
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-primary tabular-nums">
            {analytics?.all_time_win_rate ? `${analytics.all_time_win_rate}%` : "—"}
          </div>
          <div className="mt-1 text-[10px] text-faint font-sans">
            Across {analytics?.all_time_trades || 0} live trades
          </div>
        </div>

        <div className="rounded-xl border border-subtle bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between text-faint">
            <span className="text-[11px] font-bold uppercase tracking-wider">Executed Trades</span>
            <Layers className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-primary tabular-nums">
            {analytics?.all_time_trades || 0}
          </div>
          <div className="mt-1 text-[10px] text-faint font-sans">
            Fees: {fmt(analytics?.all_time_charges || 0)}
          </div>
        </div>

        <div className="rounded-xl border border-subtle bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between text-faint">
            <span className="text-[11px] font-bold uppercase tracking-wider">Portfolio Wallet</span>
            <Wallet className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-accent tabular-nums">
            {fmt(analytics?.total_wallet_balance || 0)}
          </div>
          <div className="mt-1 text-[10px] text-faint font-sans">
            Allocated: {fmt(analytics?.total_allocated_capital || 0)}
          </div>
        </div>

        <div className="rounded-xl border border-subtle bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between text-faint">
            <span className="text-[11px] font-bold uppercase tracking-wider">Online Strategies</span>
            <Award className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-primary tabular-nums">
            44 / 44
          </div>
          <div className="mt-1 text-[10px] text-faint font-sans">
            N: 14 · BN: 15 · S: 15
          </div>
        </div>
      </div>

      {/* 3. Alpha Leaders vs Drawdown Watch Podium */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top 5 Alpha Performers */}
        <div className="rounded-xl border border-subtle bg-surface p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400">
                <Flame className="h-4 w-4" />
              </div>
              <h2 className="text-sm font-bold text-primary uppercase tracking-wider">
                Top 5 Alpha Performers (Live History)
              </h2>
            </div>
            <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              HIGH WIN RATE
            </span>
          </div>

          <div className="divide-y divide-subtle/60">
            {(analytics?.top_performers || []).map((s, idx) => (
              <div key={s.strategy} className="flex items-center justify-between py-2.5 font-mono text-xs">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface2 text-[10px] font-bold text-faint">
                    #{idx + 1}
                  </span>
                  <div>
                    <div className="font-sans font-semibold text-primary">{s.strategy}</div>
                    <div className="text-[10px] text-faint">
                      {s.trades} trades · {s.win_rate}% WR
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-bull tabular-nums">
                    +{fmt(s.net_pnl)}
                  </div>
                  <div className="text-[10px] text-faint">
                    Fees: {fmt(s.charges)}
                  </div>
                </div>
              </div>
            ))}
            {(analytics?.top_performers || []).length === 0 && (
              <p className="py-6 text-center text-xs text-faint">No closed live trades recorded yet.</p>
            )}
          </div>
        </div>

        {/* Top 5 Drawdown Watch / Laggards */}
        <div className="rounded-xl border border-subtle bg-surface p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/15 text-amber-400">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <h2 className="text-sm font-bold text-primary uppercase tracking-wider">
                Laggards & Drawdown Watch
              </h2>
            </div>
            <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
              CIRCUIT BREAKER WATCH
            </span>
          </div>

          <div className="divide-y divide-subtle/60">
            {(analytics?.laggards || []).map((s, idx) => (
              <div key={s.strategy} className="flex items-center justify-between py-2.5 font-mono text-xs">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface2 text-[10px] font-bold text-faint">
                    #{idx + 1}
                  </span>
                  <div>
                    <div className="font-sans font-semibold text-primary">{s.strategy}</div>
                    <div className="text-[10px] text-faint">
                      {s.trades} trades · {s.win_rate}% WR
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-bold tabular-nums ${pnlClass(s.net_pnl)}`}>
                    {fmt(s.net_pnl)}
                  </div>
                  <div className="text-[10px] text-faint">
                    Fees: {fmt(s.charges)}
                  </div>
                </div>
              </div>
            ))}
            {(analytics?.laggards || []).length === 0 && (
              <p className="py-6 text-center text-xs text-faint">No strategy in drawdown alert state.</p>
            )}
          </div>
        </div>
      </div>

      {/* 4. Multi-Index Live Cumulative Equity Progression Curve */}
      <div className="rounded-xl border border-subtle bg-surface p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-primary uppercase tracking-wider flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-accent" />
              Live Cumulative Portfolio Growth Curve
            </h2>
            <p className="text-xs text-faint">Day-by-day realized cash additions into the strategy wallets</p>
          </div>
          <div className="flex items-center gap-3 font-mono text-xs">
            <span className="text-faint">Total Growth:</span>
            <span className={`font-bold ${pnlClass(analytics?.all_time_net_pnl || 0)}`}>
              {fmt(analytics?.all_time_net_pnl || 0)}
            </span>
          </div>
        </div>

        <div className="w-full pt-2">
          <LivePortfolioGrowthSvgChart data={analytics?.equity_curve || []} />
        </div>
      </div>

      {/* 5. 44-Strategy Quant Heatmap Matrix */}
      <div className="rounded-xl border border-subtle bg-surface p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold text-primary uppercase tracking-wider flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyan-400" />
              44-Strategy Quant Heatmap & Exposure Grid
            </h2>
            <p className="text-xs text-faint">Real-time status, active positions, and live intraday performance matrix</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono text-faint">
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-emerald-500" /> In Profit</span>
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-amber-500" /> Cost Locked / Flat</span>
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-rose-500" /> In Drawdown</span>
            <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded bg-surface3 border border-subtle" /> Idle</span>
          </div>
        </div>

        {/* Index Groups */}
        <div className="space-y-4 pt-2">
          {["NIFTY", "BANKNIFTY", "SENSEX"].map((idx) => {
            const strats = categorizedStrategies[idx] || [];
            return (
              <div key={idx} className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-2.5">
                <div className="flex items-center justify-between text-xs font-bold font-mono">
                  <span className="text-primary">{idx} ({strats.length} Strategies)</span>
                  <span className="text-faint text-[11px]">
                    {strats.filter((s) => s.state === "IN_TRADE").length} in trade
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
                  {strats.map((s) => {
                    const inTrade = s.state === "IN_TRADE";
                    const pnl = s.open_position?.trade_pnl || s.last_trade?.pnl || 0;
                    const isWin = pnl > 0;
                    const isLoss = pnl < 0;

                    let bgStyle = "bg-surface border-subtle/80 text-faint";
                    if (inTrade) {
                      if (isWin) bgStyle = "bg-emerald-500/15 border-emerald-500/40 text-emerald-400";
                      else if (isLoss) bgStyle = "bg-rose-500/15 border-rose-500/40 text-rose-400";
                      else bgStyle = "bg-amber-500/15 border-amber-500/40 text-amber-400";
                    }

                    return (
                      <div
                        key={s.strategy}
                        className={`rounded-lg border p-2 font-mono text-[11px] transition hover:scale-[1.02] ${bgStyle}`}
                      >
                        <div className="truncate font-sans font-semibold text-primary" title={s.strategy}>
                          {s.strategy.replace(`${idx}_`, "")}
                        </div>
                        <div className="mt-1 flex items-center justify-between text-[10px]">
                          <span className="text-faint">{inTrade ? "IN TRADE" : "IDLE"}</span>
                          <span className={`font-bold tabular-nums ${inTrade ? (isWin ? "text-bull" : isLoss ? "text-bear" : "text-amber-400") : "text-faint"}`}>
                            {inTrade ? (pnl >= 0 ? `+₹${pnl.toFixed(0)}` : `₹${pnl.toFixed(0)}`) : "—"}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
