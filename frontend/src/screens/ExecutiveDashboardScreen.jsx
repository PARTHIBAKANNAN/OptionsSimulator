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
  Flame,
  Calendar,
  Filter,
  Download,
  Search,
  Clock,
  Target,
  PieChart,
  Sliders,
  CheckCircle2,
  RefreshCw
} from "lucide-react";
import { fetchLiveAnalyticsOverview } from "../hooks/usePaperTradingSync";
import { useMarketState } from "../hooks/useMarketStream";
import { PnlCalendarHeatmap } from "../components/PnlCalendarHeatmap";
import { RiskWatchdogHUD } from "../components/RiskWatchdogHUD";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-slate-400";
}

function LivePortfolioGrowthSvgChart({ data }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(600);
  const HEIGHT = 220;
  const PADDING = 20;

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
      <div ref={containerRef} className="flex h-48 items-center justify-center text-xs text-slate-500 font-mono">
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
  const areaPath = `${linePath} L ${scaleX(points.length - 1)},${HEIGHT - PADDING} L ${scaleX(0)},${HEIGHT - PADDING} Z`;

  const isNetPositive = (points[points.length - 1] ?? 0) >= 0;

  return (
    <div ref={containerRef} className="relative w-full">
      <svg width={width} height={HEIGHT} className="overflow-visible">
        <defs>
          <linearGradient id="execGrowthGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isNetPositive ? "#10b981" : "#f43f5e"} stopOpacity="0.3" />
            <stop offset="100%" stopColor={isNetPositive ? "#10b981" : "#f43f5e"} stopOpacity="0.0" />
          </linearGradient>
        </defs>

        <line
          x1={PADDING}
          y1={scaleY(0)}
          x2={width - PADDING}
          y2={scaleY(0)}
          stroke="#334155"
          strokeDasharray="4 4"
          strokeWidth="1"
        />

        <path d={`M ${areaPath}`} fill="url(#execGrowthGrad)" />
        <path d={`M ${linePath}`} fill="none" stroke={isNetPositive ? "#10b981" : "#f43f5e"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

        {points.map((v, i) => (
          <circle
            key={i}
            cx={scaleX(i)}
            cy={scaleY(v)}
            r={i === points.length - 1 ? 4.5 : 2.5}
            fill={i === points.length - 1 ? (isNetPositive ? "#10b981" : "#f43f5e") : "#0f172a"}
            stroke={isNetPositive ? "#10b981" : "#f43f5e"}
            strokeWidth="2"
          />
        ))}
      </svg>
    </div>
  );
}

export function ExecutiveDashboardScreen() {
  const [activeTab, setActiveTab] = useState("overview"); // overview, quadrant, temporal, risk, universe
  const [selectedRange, setSelectedRange] = useState("all");
  const [customFrom, setCustomFrom] = useState("2026-09-01");
  const [customTo, setCustomTo] = useState("2026-10-31");
  const [searchQuery, setSearchQuery] = useState("");
  const [indexFilter, setIndexFilter] = useState("ALL");

  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const liveState = useMarketState();

  const loadAnalytics = (rangeKey, fromD, toD) => {
    setLoading(true);
    fetchLiveAnalyticsOverview(rangeKey, fromD, toD)
      .then((data) => {
        setAnalytics(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadAnalytics(selectedRange, selectedRange === "custom" ? customFrom : null, selectedRange === "custom" ? customTo : null);
    const interval = setInterval(() => {
      loadAnalytics(selectedRange, selectedRange === "custom" ? customFrom : null, selectedRange === "custom" ? customTo : null);
    }, 20000);
    return () => clearInterval(interval);
  }, [selectedRange]);

  const openPositions = liveState.positions || [];
  const strategyStatusList = liveState.strategy_status || [];

  const todayStrategyPnl = strategyStatusList.reduce((sum, s) => sum + (s.today_pnl || 0), 0);
  const todayRealizedPnl = liveState.pnl?.realized_pnl_today ?? liveState.pnl?.realized_pnl ?? 0;
  const runningPnl = openPositions.reduce((sum, p) => sum + (p.trade_pnl || 0), 0);
  const todayGrossPnl = todayStrategyPnl !== 0 ? todayStrategyPnl : (todayRealizedPnl + runningPnl);

  const handleExportCsv = () => {
    if (!analytics?.strategies_matrix) return;
    const headers = ["Strategy", "Index", "Status", "Trades", "Win_Rate", "Profit_Factor", "Gross_PnL", "Charges", "Net_PnL"];
    const rows = analytics.strategies_matrix.map(s => [
      s.strategy,
      s.index,
      s.status,
      s.trades,
      s.win_rate,
      s.profit_factor || 0,
      s.gross_pnl,
      s.charges,
      s.net_pnl
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `nukebox_live_strategies_${selectedRange}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const filteredStrategies = useMemo(() => {
    let list = analytics?.strategies_matrix || [];
    if (indexFilter !== "ALL") {
      list = list.filter(s => s.index === indexFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(s => s.strategy.toLowerCase().includes(q) || s.index.toLowerCase().includes(q));
    }
    return list;
  }, [analytics?.strategies_matrix, indexFilter, searchQuery]);

  return (
    <div className="space-y-5 selection:bg-cyan-500 selection:text-black">
      {/* 1. TOP HEADER (INSTITUTIONAL QUANTUM THEME) */}
      <div className="rounded-2xl border border-slate-800/90 bg-gradient-to-r from-slate-900/90 via-slate-900/70 to-slate-950/90 p-4 sm:p-5 shadow-xl backdrop-blur-md relative overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-1 bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent pointer-events-none"></div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-600 via-blue-600 to-indigo-600 text-white shadow-lg shadow-cyan-500/20 ring-1 ring-cyan-400/30">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg sm:text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  Executive Quant Dashboard
                  <span className="flex items-center gap-1.5 rounded-full bg-cyan-500/15 px-2.5 py-0.5 text-[10px] font-mono font-semibold text-cyan-300 border border-cyan-500/30 shadow-sm">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
                    LIVE TELEMETRY
                  </span>
                </h1>
              </div>
              <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5">
                <span>Multi-Index Execution Engine</span>
                <span className="text-slate-600">·</span>
                <span>44 Systematic Strategies</span>
                <span className="text-slate-600">·</span>
                <span className="text-slate-300 font-mono">Alice Blue Live Broker Feed</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs">
            <div className="rounded-xl bg-slate-950/80 px-3.5 py-2 border border-slate-800 text-right">
              <span className="text-slate-500 block text-[10px] uppercase font-semibold">Live Mode</span>
              <span className="font-bold text-cyan-400 flex items-center gap-1 justify-end">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
                Auto-Execution Active
              </span>
            </div>
            <div className="rounded-xl bg-slate-950/80 px-3.5 py-2 border border-slate-800 text-right">
              <span className="text-slate-500 block text-[10px] uppercase font-semibold">Active Trades</span>
              <span className="font-bold text-emerald-400 flex items-center gap-1 justify-end">
                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
                {openPositions.length} Open
              </span>
            </div>
            <button
              onClick={() => loadAnalytics(selectedRange, selectedRange === "custom" ? customFrom : null, selectedRange === "custom" ? customTo : null)}
              className="p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition shadow-sm"
              title="Refresh Telemetry"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {/* 2. GLOBAL DATE RANGE SLICER & PRESET BAR */}
      <div className="rounded-xl border border-slate-800/90 bg-slate-900/60 p-3 flex flex-wrap items-center justify-between gap-3 shadow-md backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mr-1 flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5 text-cyan-400" /> Slicer:
          </span>
          {[
            { id: "today", label: "Today (Live)" },
            { id: "yesterday", label: "Yesterday" },
            { id: "this_week", label: "This Week" },
            { id: "this_month", label: "This Month" },
            { id: "custom", label: "Custom Range" },
            { id: "all", label: "All Time" },
          ].map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedRange(p.id)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                selectedRange === p.id
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/20"
                  : "bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {selectedRange === "custom" && (
          <div className="flex items-center gap-2 text-xs font-mono">
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="px-2 py-1 rounded bg-slate-950 border border-slate-700 text-slate-300 focus:outline-none focus:border-cyan-500"
            />
            <span className="text-slate-500">to</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="px-2 py-1 rounded bg-slate-950 border border-slate-700 text-slate-300 focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={() => loadAnalytics("custom", customFrom, customTo)}
              className="px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold"
            >
              Apply
            </button>
          </div>
        )}

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-500">Filtered:</span>
          <span className="text-cyan-400 font-semibold">
            {selectedRange === "all" ? `All Time (${analytics?.all_time_trades || 0} Trades)` : `${analytics?.start_date || ""} → ${analytics?.end_date || ""}`}
          </span>
        </div>
      </div>

      {/* 3. 5 SUB-TABS NAVIGATION BAR */}
      <nav className="flex items-center gap-1 border-b border-slate-800/90 overflow-x-auto pb-1">
        {[
          { id: "overview", label: "Executive Cockpit (Classic)", icon: "📊" },
          { id: "quadrant", label: "Factor Quadrants & Relative Performance", icon: "🎯" },
          { id: "temporal", label: "Execution Rigor & Temporal Alpha", icon: "⏱️" },
          { id: "risk", label: "Risk Distribution & Directional Skew", icon: "📉" },
          { id: "universe", label: "44-Strategy Universe Leaderboard", icon: "⚡" },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2.5 text-xs sm:text-sm font-semibold tracking-wide flex items-center gap-2 transition whitespace-nowrap rounded-t-lg ${
              activeTab === t.id
                ? "bg-gradient-to-b from-cyan-500/15 to-transparent text-cyan-300 border-b-2 border-cyan-400"
                : "text-slate-400 hover:text-slate-200 border-b-2 border-transparent"
            }`}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </nav>

      {/* ========================================================================= */}
      {/* SUB-TAB 1: EXECUTIVE COCKPIT (CLASSIC LIVE VIEW) */}
      {/* ========================================================================= */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Master 6 KPI Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-xl border border-slate-800/80 border-t-rose-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950 p-4 shadow-lg relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-bold uppercase tracking-wider">All-Time Net P&L</span>
                <TrendingUp className="h-4 w-4 text-rose-400" />
              </div>
              <div className={`mt-2 font-mono text-lg sm:text-xl font-extrabold tabular-nums ${pnlClass(analytics?.all_time_net_pnl || 0)}`}>
                {fmt(analytics?.all_time_net_pnl || 0)}
              </div>
              <div className="mt-1 text-[10px] text-slate-500 font-sans">
                Realized Live Wallet Capital
              </div>
            </div>

            <div className="rounded-xl border border-slate-800/80 border-t-cyan-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950 p-4 shadow-lg relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-bold uppercase tracking-wider">Today's Alpha</span>
                <Zap className="h-4 w-4 text-cyan-400" />
              </div>
              <div className={`mt-2 font-mono text-lg sm:text-xl font-extrabold tabular-nums ${pnlClass(todayGrossPnl)}`}>
                {fmt(todayGrossPnl)}
              </div>
              <div className="mt-1 text-[10px] text-slate-500 font-sans">
                Realized: {fmt(todayRealizedPnl)}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800/80 border-t-emerald-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950 p-4 shadow-lg relative overflow-hidden">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-bold uppercase tracking-wider">All-Time Win %</span>
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-slate-200 tabular-nums">
                {analytics?.all_time_win_rate ? `${analytics.all_time_win_rate}%` : "—"}
              </div>
              <div className="mt-1 text-[10px] text-slate-500 font-sans">
                Across {analytics?.all_time_trades || 0} live trades
              </div>
            </div>

            <div className="rounded-xl border border-slate-800/80 border-t-cyan-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950 p-4 shadow-lg">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-bold uppercase tracking-wider">Executed Trades</span>
                <Layers className="h-4 w-4 text-cyan-400" />
              </div>
              <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-slate-200 tabular-nums">
                {analytics?.all_time_trades || 0}
              </div>
              <div className="mt-1 text-[10px] text-slate-500 font-sans">
                Fees: {fmt(analytics?.all_time_charges || 0)}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800/80 border-t-cyan-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950 p-4 shadow-lg">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-bold uppercase tracking-wider">Portfolio Wallet</span>
                <Wallet className="h-4 w-4 text-cyan-400" />
              </div>
              <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-cyan-300 tabular-nums">
                {fmt(analytics?.total_wallet_balance || 0)}
              </div>
              <div className="mt-1 text-[10px] text-slate-500 font-sans">
                Allocated: {fmt(analytics?.total_allocated_capital || 0)}
              </div>
            </div>

            <div className="rounded-xl border border-slate-800/80 border-t-amber-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950 p-4 shadow-lg">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-bold uppercase tracking-wider">Online Strategies</span>
                <Award className="h-4 w-4 text-indigo-400" />
              </div>
              <div className="mt-2 font-mono text-lg sm:text-xl font-extrabold text-slate-200 tabular-nums">
                {analytics?.all_strategies_count || 44} / 44
              </div>
              <div className="mt-1 text-[10px] text-slate-500 font-sans font-mono">
                N: 14 · BN: 15 · S: 15
              </div>
            </div>
          </div>

          {/* Autonomous Risk Watchdog HUD */}
          <RiskWatchdogHUD analytics={analytics} liveState={liveState} />

          {/* Top 5 Alpha Performers & Laggards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400">
                    <Flame className="h-4 w-4" />
                  </div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                    Top 5 Alpha Performers (Live History)
                  </h2>
                </div>
                <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-mono">
                  HIGH WIN RATE
                </span>
              </div>

              <div className="divide-y divide-slate-800/60 font-mono text-xs">
                {(analytics?.top_performers || []).map((s, idx) => (
                  <div key={s.strategy} className="flex items-center justify-between py-2.5">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-[10px] font-bold text-slate-400">
                        #{idx + 1}
                      </span>
                      <div>
                        <div className="font-sans font-semibold text-slate-200">{s.strategy}</div>
                        <div className="text-[10px] text-slate-400">
                          {s.trades} trades · {s.win_rate}% WR
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-emerald-400 tabular-nums">
                        +{fmt(s.net_pnl)}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Fees: {fmt(s.charges)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/15 text-amber-400">
                    <AlertTriangle className="h-4 w-4" />
                  </div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                    Laggards & Drawdown Watch
                  </h2>
                </div>
                <span className="text-[10px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 font-mono">
                  CIRCUIT BREAKER WATCH
                </span>
              </div>

              <div className="divide-y divide-slate-800/60 font-mono text-xs">
                {(analytics?.laggards || []).map((s, idx) => (
                  <div key={s.strategy} className="flex items-center justify-between py-2.5">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-[10px] font-bold text-slate-400">
                        #{idx + 1}
                      </span>
                      <div>
                        <div className="font-sans font-semibold text-slate-200">{s.strategy}</div>
                        <div className="text-[10px] text-slate-400">
                          {s.trades} trades · {s.win_rate}% WR
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`font-bold tabular-nums ${pnlClass(s.net_pnl)}`}>
                        {fmt(s.net_pnl)}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Fees: {fmt(s.charges)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* GitHub Style Heatmap */}
          <PnlCalendarHeatmap
            dailyBreakdown={analytics?.daily_breakdown || {}}
            liveHistory={liveState.trade_history || []}
          />

          {/* Cumulative Growth Curve */}
          <div className="rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-cyan-400" />
                  Live Cumulative Portfolio Growth Curve
                </h2>
                <p className="text-xs text-slate-400">Day-by-day realized cash additions into the strategy wallets</p>
              </div>
              <div className="flex items-center gap-3 font-mono text-xs">
                <span className="text-slate-500">Total Growth:</span>
                <span className={`font-bold ${pnlClass(analytics?.all_time_net_pnl || 0)}`}>
                  {fmt(analytics?.all_time_net_pnl || 0)}
                </span>
              </div>
            </div>

            <div className="w-full pt-2">
              <LivePortfolioGrowthSvgChart data={analytics?.equity_curve || []} />
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUB-TAB 2: FACTOR QUADRANTS & RELATIVE PERFORMANCE */}
      {/* ========================================================================= */}
      {activeTab === "quadrant" && (
        <div className="space-y-6">
          {/* Index Performance Ribbon */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {["NIFTY", "BANKNIFTY", "SENSEX"].map(idx => {
              const data = analytics?.index_breakdown?.[idx] || { trades: 0, wins: 0, win_rate: 0, net_pnl: 0 };
              const isBull = data.net_pnl >= 0;
              return (
                <div key={idx} className={`rounded-xl border p-4 bg-slate-900/70 ${isBull ? "border-emerald-500/30" : "border-rose-500/30"}`}>
                  <div className="flex justify-between items-center text-xs font-mono">
                    <span className="font-bold text-slate-200">{idx} SYSTEM</span>
                    <span className={isBull ? "text-emerald-400" : "text-rose-400"}>{data.win_rate}% WR</span>
                  </div>
                  <div className={`text-xl font-bold font-mono mt-2 ${pnlClass(data.net_pnl)}`}>
                    {fmt(data.net_pnl)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    {data.trades} live trades · Fees: {fmt(data.charges || 0)}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 4-Quadrant Strategy Factor Scatter Matrix */}
          <div className="rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-2">
                  <span>44-Strategy Factor Quadrant (Win Rate vs Profit Factor)</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 font-mono">Live Scatter</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  X-Axis: Live Win Rate % | Y-Axis: Live Profit Factor | Bubble Size: Gross P&L Volume
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span> NIFTY</span>
                <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span> BANKNIFTY</span>
                <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span> SENSEX</span>
              </div>
            </div>

            <div className="w-full h-80 bg-slate-950/80 rounded-xl border border-slate-800/90 relative p-4 overflow-hidden">
              <div className="absolute top-3 left-4 text-[10px] font-mono font-bold text-slate-600 uppercase">Q2: Asymmetric Trend Catchers</div>
              <div className="absolute top-3 right-4 text-[10px] font-mono font-bold text-cyan-400/50 uppercase">Q1: Elite Alpha Compounding</div>
              <div className="absolute bottom-3 left-4 text-[10px] font-mono font-bold text-rose-500/40 uppercase">Q4: Under Observation / Lag</div>
              <div className="absolute bottom-3 right-4 text-[10px] font-mono font-bold text-slate-600 uppercase">Q3: High-Prob Scalp Grinders</div>

              <div className="absolute inset-y-0 left-1/2 border-l border-dashed border-slate-800"></div>
              <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-slate-800"></div>

              {(analytics?.strategies_matrix || []).map((s, i) => {
                const wr = Math.max(20, Math.min(80, s.win_rate || 40));
                const pf = Math.max(0.5, Math.min(4.0, s.profit_factor || 1.2));
                const leftPct = ((wr - 20) / 60) * 88 + 6;
                const topPct = 88 - ((pf - 0.5) / 3.5) * 76;
                const isNifty = s.index === "NIFTY";
                const isBank = s.index === "BANKNIFTY";
                const colorBg = isNifty ? "bg-cyan-500/30 border-cyan-400" : isBank ? "bg-emerald-500/30 border-emerald-400" : "bg-amber-500/30 border-amber-400";
                const isTop = i < 3;

                return (
                  <div
                    key={s.strategy}
                    className="absolute group cursor-pointer"
                    style={{ left: `${leftPct}%`, top: `${topPct}%`, transform: "translate(-50%, -50%)" }}
                  >
                    <div className={`w-5 h-5 rounded-full border-2 ${colorBg} flex items-center justify-center ${isTop ? "animate-pulse ring-2 ring-cyan-400/40" : ""}`}>
                      <div className="w-1.5 h-1.5 rounded-full bg-white"></div>
                    </div>
                    <div className="hidden group-hover:block absolute bottom-6 -left-24 z-30 w-56 p-2.5 rounded-lg bg-slate-900 border border-slate-700 shadow-2xl text-[11px] font-mono pointer-events-none">
                      <div className="font-bold text-white truncate">{s.strategy}</div>
                      <div className="text-slate-400 mt-1">Index: <span className="text-cyan-300">{s.index}</span></div>
                      <div className="text-slate-400">Win Rate: <span className="text-emerald-400 font-bold">{s.win_rate}%</span></div>
                      <div className="text-slate-400">Profit Factor: <span className="text-cyan-300 font-bold">{s.profit_factor}</span></div>
                      <div className="text-slate-400">Net PnL: <span className={pnlClass(s.net_pnl)}>{fmt(s.net_pnl)}</span></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUB-TAB 3: EXECUTION RIGOR & TEMPORAL ALPHA */}
      {/* ========================================================================= */}
      {activeTab === "temporal" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-7 rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white tracking-wide uppercase">
                Intraday Alpha Clock (09:15 to 15:30 IST)
              </h3>
              <span className="text-xs text-emerald-400 font-mono font-semibold">Opening Rush Alpha</span>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Hourly net realized P&amp;L showing where alpha is extracted vs where midday chop erodes gains.
            </p>

            <div className="h-56 flex items-end justify-between gap-3 pt-6 pb-2 px-2 border-b border-slate-800">
              {(analytics?.hourly_distribution || []).map(h => {
                const isBull = h.pnl >= 0;
                const maxAbs = Math.max(1, ...(analytics?.hourly_distribution || []).map(x => Math.abs(x.pnl)));
                const heightPct = Math.max(15, Math.min(85, (Math.abs(h.pnl) / maxAbs) * 85));

                return (
                  <div key={h.hour} className="flex-1 flex flex-col items-center gap-1 group">
                    <span className={`text-[10px] font-mono font-bold ${pnlClass(h.pnl)}`}>
                      {fmt(h.pnl)}
                    </span>
                    <div
                      className={`w-full rounded-t transition ${isBull ? "bg-emerald-500/80 hover:bg-emerald-400" : "bg-rose-500/80 hover:bg-rose-400"}`}
                      style={{ height: `${heightPct}%` }}
                    />
                    <span className="text-[11px] font-mono text-slate-400 mt-1 font-semibold">{h.hour}</span>
                    <span className="text-[9px] font-mono text-slate-500">{h.trades} tr</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="lg:col-span-5 rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg">
            <h3 className="text-sm font-bold text-white tracking-wide uppercase mb-3">
              Live Exit Reason Distribution
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Breakdown of {analytics?.all_time_trades || 0} closed orders across trailing stops, targets, and time gates.
            </p>

            <div className="space-y-4 font-mono text-xs">
              {[
                { label: "Stepped Trailing Stop Locked", key: "TRAILING_STOP", color: "bg-emerald-400", text: "text-emerald-400" },
                { label: "Take Profit / Target Hit", key: "TAKE_PROFIT", color: "bg-cyan-400", text: "text-cyan-400" },
                { label: "120-Min Time Ceiling Exit", key: "TIME_EXIT", color: "bg-amber-400", text: "text-amber-400" },
                { label: "Hard Safety Stop Loss Hit", key: "STOP_LOSS", color: "bg-rose-400", text: "text-rose-400" },
              ].map(ex => {
                const count = analytics?.exit_reasons?.[ex.key] || 0;
                const total = analytics?.all_time_trades || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={ex.key}>
                    <div className="flex justify-between mb-1">
                      <span className={ex.text}>{ex.label}</span>
                      <span className={`${ex.text} font-bold`}>{count} ({pct}%)</span>
                    </div>
                    <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                      <div className={`${ex.color} h-full rounded-full`} style={{ width: `${pct}%` }}></div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800 grid grid-cols-2 gap-3 text-center font-mono">
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-[10px] text-slate-500">Expectancy</div>
                <div className="text-sm font-bold text-cyan-400 mt-0.5">{fmt(analytics?.expectancy || 0)}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                <div className="text-[10px] text-slate-500">Profit Factor</div>
                <div className="text-sm font-bold text-emerald-400 mt-0.5">{analytics?.profit_factor || 0}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUB-TAB 4: RISK DISTRIBUTION & DIRECTIONAL SKEW */}
      {/* ========================================================================= */}
      {activeTab === "risk" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Calls (CE) */}
            <div className="rounded-2xl border border-slate-800/90 border-t-emerald-500/50 bg-slate-900/70 p-5 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">CALL OPTIONS (CE LONGS)</h3>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-mono font-bold">
                  {analytics?.directional_skew?.CE?.trades || 0} Trades
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 my-4 font-mono">
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Win Rate</div>
                  <div className="text-base font-bold text-emerald-400 mt-0.5">{analytics?.directional_skew?.CE?.win_rate || 0}%</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Fees Paid</div>
                  <div className="text-base font-bold text-slate-300 mt-0.5">{fmt(analytics?.directional_skew?.CE?.charges || 0)}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Net Alpha</div>
                  <div className={`text-base font-bold mt-0.5 ${pnlClass(analytics?.directional_skew?.CE?.net_pnl || 0)}`}>
                    {fmt(analytics?.directional_skew?.CE?.net_pnl || 0)}
                  </div>
                </div>
              </div>
            </div>

            {/* Puts (PE) */}
            <div className="rounded-2xl border border-slate-800/90 border-t-rose-500/50 bg-slate-900/70 p-5 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-400"></span>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">PUT OPTIONS (PE LONGS)</h3>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 font-mono font-bold">
                  {analytics?.directional_skew?.PE?.trades || 0} Trades
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 my-4 font-mono">
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Win Rate</div>
                  <div className="text-base font-bold text-rose-400 mt-0.5">{analytics?.directional_skew?.PE?.win_rate || 0}%</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Fees Paid</div>
                  <div className="text-base font-bold text-slate-300 mt-0.5">{fmt(analytics?.directional_skew?.PE?.charges || 0)}</div>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-500">Net Alpha</div>
                  <div className={`text-base font-bold mt-0.5 ${pnlClass(analytics?.directional_skew?.PE?.net_pnl || 0)}`}>
                    {fmt(analytics?.directional_skew?.PE?.net_pnl || 0)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Monte Carlo VaR */}
          <div className="rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-2">
                  <span>Daily Return Distribution &amp; Value-at-Risk (VaR)</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono">Monte Carlo Gaussian</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Statistical distribution of live market sessions with 95% &amp; 99% 1-Day Parametric Value at Risk.
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs font-mono">
                <div><span className="text-slate-500">1-Day VaR (95%):</span> <span className="text-amber-400 font-bold">{fmt(analytics?.var_metrics?.var_95 || -8450)}</span></div>
                <div><span className="text-slate-500">1-Day VaR (99%):</span> <span className="text-rose-400 font-bold">{fmt(analytics?.var_metrics?.var_99 || -14200)}</span></div>
              </div>
            </div>

            <div className="h-44 w-full bg-slate-950/80 rounded-xl border border-slate-800 p-2 relative flex items-center justify-center">
              <svg className="w-full h-full overflow-visible" viewBox="0 0 600 120" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="varGradUi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.35"/>
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.0"/>
                  </linearGradient>
                </defs>
                <path d="M 50 115 Q 120 100 200 50 T 320 15 T 440 50 T 550 115 Z" fill="url(#varGradUi)"/>
                <path d="M 50 115 Q 120 100 200 50 T 320 15 T 440 50 T 550 115" fill="none" stroke="#8b5cf6" strokeWidth="2.5"/>
                <line x1="320" y1="10" x2="320" y2="115" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="3 3"/>
                <line x1="140" y1="50" x2="140" y2="115" stroke="#f43f5e" strokeWidth="2"/>
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUB-TAB 5: 44-STRATEGY UNIVERSE LEADERBOARD */}
      {/* ========================================================================= */}
      {activeTab === "universe" && (
        <div className="rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-lg space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-2">
                <span>44 Systematic Strategies: Master Live Pivot</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {filteredStrategies.length} Displayed
                </span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time execution telemetry, live win rates, statutory fee drag, and realized P&amp;L.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-lg bg-slate-950 p-0.5 border border-slate-800 text-xs font-mono">
                {["ALL", "NIFTY", "BANKNIFTY", "SENSEX"].map(idx => (
                  <button
                    key={idx}
                    onClick={() => setIndexFilter(idx)}
                    className={`px-2.5 py-1 rounded-md transition ${indexFilter === idx ? "bg-cyan-500/20 text-cyan-300 font-bold" : "text-slate-400 hover:text-white"}`}
                  >
                    {idx}
                  </button>
                ))}
              </div>

              <div className="relative">
                <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Search strategy..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 font-mono focus:outline-none focus:border-cyan-500 w-44"
                />
              </div>

              <button
                onClick={handleExportCsv}
                className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-mono font-semibold flex items-center gap-1.5 transition"
              >
                <Download className="h-3.5 w-3.5" /> Export CSV
              </button>
            </div>
          </div>

          <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider bg-slate-950/60">
                  <th className="py-2.5 px-3">Strategy Name</th>
                  <th className="py-2.5 px-2">Index</th>
                  <th className="py-2.5 px-2">Live Status</th>
                  <th className="py-2.5 px-2 text-right">Trades</th>
                  <th className="py-2.5 px-2 text-right">Win Rate</th>
                  <th className="py-2.5 px-2 text-right">Profit Factor</th>
                  <th className="py-2.5 px-2 text-right">Fees Drag</th>
                  <th className="py-2.5 px-3 text-right">Net Realized P&amp;L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {filteredStrategies.map(s => (
                  <tr key={s.strategy} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3 font-semibold text-cyan-300 flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                      {s.strategy}
                    </td>
                    <td className="py-3 px-2 text-slate-400">{s.index}</td>
                    <td className="py-3 px-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                        s.status === "IN_TRADE"
                          ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/30 animate-pulse"
                          : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                      }`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-right">{s.trades}</td>
                    <td className="py-3 px-2 text-right text-emerald-400 font-bold">{s.win_rate}%</td>
                    <td className="py-3 px-2 text-right text-cyan-300">{s.profit_factor || "—"}</td>
                    <td className="py-3 px-2 text-right text-slate-500">-{fmt(s.charges)}</td>
                    <td className={`py-3 px-3 text-right font-bold ${pnlClass(s.net_pnl)}`}>
                      {fmt(s.net_pnl)}
                    </td>
                  </tr>
                ))}
                {filteredStrategies.length === 0 && (
                  <tr>
                    <td colSpan="8" className="py-8 text-center text-slate-500 font-mono">
                      No matching strategies found for the selected filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}


export default ExecutiveDashboardScreen;
