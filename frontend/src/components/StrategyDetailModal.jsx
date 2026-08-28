import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Layers, Cpu, Compass, ShieldCheck, Wallet, ArrowUpRight, ArrowDownRight } from "lucide-react";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function MiniEquityCurve({ days }) {
  if (!days || days.length < 2) {
    return <div className="flex h-24 items-center justify-center text-xs text-faint font-sans">Not enough points for mini equity curve</div>;
  }
  const width = 800, height = 100, pad = 8;
  const values = days.map((d) => d.cumulative_pnl);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const range = max - min || 1;
  const xStep = (width - pad * 2) / (values.length - 1);
  const toXY = (v, i) => [pad + i * xStep, height - pad - ((v - min) / range) * (height - pad * 2)];
  const linePath = values.map((v, i) => toXY(v, i).join(",")).join(" L ");
  const positive = values[values.length - 1] >= 0;
  const areaPath = `M ${pad},${height - pad} L ${linePath} L ${pad + (values.length - 1) * xStep},${height - pad} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-24 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="modalEquityFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0.35" />
          <stop offset="100%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#modalEquityFill)" />
      <path d={`M ${linePath}`} fill="none" stroke={positive ? "#22c55e" : "#ef4444"} strokeWidth="2" />
    </svg>
  );
}

const STRATEGY_SPECS = {
  NIFTY_ORB_BULLISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Call",
    profile: "Opening Breakout Alpha",
    indicators: ["Opening Range (ORB)", "Exponential Moving Average (EMA)", "Cumulative Volume Delta (CVD)"],
    summary: "Captures morning opening range momentum following initial price discovery, filtering false breakouts with higher-timeframe trend alignment.",
    overview: "Monitors opening volatility across primary index constituents to identify high-conviction breakout opportunities. Uses adaptive trailing risk rules to lock in profits during rapid momentum expansions.",
    riskProfile: "Fixed percentage risk guardrail with multi-tiered stepped trailing profit ratchet.",
  },
  NIFTY_ORB_BEARISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Put",
    profile: "Opening Breakdown Alpha",
    indicators: ["Opening Range (ORB)", "Exponential Moving Average (EMA)", "Cumulative Volume Delta (CVD)"],
    summary: "Executes directional downside breakdowns when opening order flow velocity indicates aggressive institutional distribution.",
    overview: "Identifies early session breakdown patterns below key price levels, riding downside momentum while enforcing strict time-based exit limits.",
    riskProfile: "Fixed percentage risk guardrail with multi-tiered stepped trailing profit ratchet.",
  },
  NIFTY_EMA_BOUNCE_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Call",
    profile: "Trend Continuation Pullback",
    indicators: ["Exponential Moving Average (EMA)", "Relative Strength Index (RSI)", "Price Action Reversals"],
    summary: "Enters high-probability pullback entries testing institutional dynamic support levels during established uptrends.",
    overview: "Capitalizes on short-term price pullbacks within stronger macro uptrends. Trades mean-reversion bounces back toward dominant trend direction.",
    riskProfile: "Automated trailing profit ratchet with defined stop loss protection.",
  },
  NIFTY_EMA_REJECTION_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Put",
    profile: "Trend Continuation Rejection",
    indicators: ["Exponential Moving Average (EMA)", "Relative Strength Index (RSI)", "Price Action Reversals"],
    summary: "Capitalizes on overhead resistance rejections aligned with primary downward trend momentum.",
    overview: "Systematically executes downside position entries when relief rallies fail at key dynamic resistance zones.",
    riskProfile: "Automated trailing profit ratchet with defined stop loss protection.",
  },
  DEFAULT: {
    timeframe: "5-Minute / 1-Minute",
    index: "Index Derivatives (NIFTY / SENSEX / BANKNIFTY)",
    strikeMode: "Delta-Optimized Options",
    profile: "Systematic Quantitative Model",
    indicators: ["Exponential Moving Average (EMA)", "Moving Average Convergence Divergence (MACD)", "Volume Delta Filter"],
    summary: "Systematic non-discretionary algorithmic execution model engineered for Indian index options microstructure.",
    overview: "Evaluates multi-timeframe price discovery, momentum alignment, and structural volatility parameters to execute disciplined directional trades.",
    riskProfile: "Standard institutional risk parameters including stop loss limits, stepped profit locks, and time-decay holding caps.",
  },
};

export function StrategyDetailModal({ strategy, onClose }) {
  if (!strategy) return null;

  const strategyObj = typeof strategy === "object" ? strategy : { strategy };
  const name = strategyObj.strategy || strategyObj.name || "STRATEGY";
  const spec = STRATEGY_SPECS[name] || STRATEGY_SPECS.DEFAULT;
  const isCE = name.includes("BULLISH") || name.includes("CE") || name.includes("BOUNCE");
  const capital = strategyObj.capital;
  const daily = strategyObj.daily;

  return createPortal(
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/80 p-3 sm:p-5 backdrop-blur-md"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="flex max-h-[88vh] w-full max-w-3xl flex-col rounded-3xl border border-subtle bg-surface p-5 sm:p-7 shadow-2xl overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.96, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 15 }}
          transition={{ duration: 0.18 }}
        >
          {/* Header */}
          <div className="flex items-start justify-between border-b border-subtle pb-4 mb-5">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-black border ${
                  isCE ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : "bg-rose-500/15 text-rose-400 border-rose-500/30"
                }`}>
                  {isCE ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                  {isCE ? "BULLISH (CE)" : "BEARISH (PE)"}
                </span>
                <span className="rounded-full bg-surface3 px-2 py-0.5 text-[10px] font-mono font-bold text-gray-300 border border-subtle">
                  {spec.timeframe}
                </span>
              </div>
              <h2 className="text-base sm:text-lg font-black text-white tracking-tight">{name}</h2>
              <p className="text-xs text-gray-400 mt-0.5">{spec.index} • {spec.strikeMode}</p>
            </div>

            <button
              onClick={onClose}
              className="rounded-full p-2 text-faint hover:bg-surface2 hover:text-primary transition"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Body Content */}
          <div className="space-y-4 text-xs font-sans leading-relaxed">
            {/* Capital Requirements & Drawdown Metrics */}
            {capital && (
              <div className="rounded-2xl border border-subtle bg-surface2/60 p-4 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm text-white">
                  <Wallet className="h-4 w-4 text-accent" />
                  <span>Allocated Capital &amp; Risk Requirements</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
                  <div className="rounded-xl border border-subtle bg-surface p-3">
                    <span className="text-[10px] font-semibold uppercase text-faint block">Trade Margin + Buffer</span>
                    <span className="font-mono text-sm font-bold text-primary">{fmtRupee(capital.avg_trade_risk)}</span>
                  </div>
                  <div className="rounded-xl border border-subtle bg-surface p-3">
                    <span className="text-[10px] font-semibold uppercase text-faint block">Max Historical Drawdown</span>
                    <span className="font-mono text-sm font-bold text-bear">{fmtRupee(capital.max_historical_drawdown)}</span>
                  </div>
                  <div className="rounded-xl border border-subtle bg-surface p-3">
                    <span className="text-[10px] font-semibold uppercase text-faint block">Recommended Capital</span>
                    <span className="font-mono text-sm font-bold text-accent">{fmtRupee(capital.recommended_capital)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Historical Equity Growth Curve */}
            {daily && daily.length > 1 && (
              <div className="rounded-2xl border border-subtle bg-surface2/60 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm text-white">Historical Backtest Equity Growth</span>
                  <span className="font-mono text-xs text-emerald-400 font-bold">1-Year Historical Track Record</span>
                </div>
                <MiniEquityCurve days={daily} />
              </div>
            )}

            {/* Core Quantitative Indicators Used (Names Only - Zero Math/Logic) */}
            <div className="rounded-2xl border border-subtle bg-surface2/40 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-white">
                <Cpu className="h-4 w-4 text-accent" />
                <span>Quantitative Indicators Used</span>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                {spec.indicators.map((indName, idx) => (
                  <span key={idx} className="rounded-lg bg-surface border border-subtle px-3 py-1.5 font-mono text-xs font-semibold text-cyan-400">
                    {indName}
                  </span>
                ))}
              </div>
            </div>

            {/* Strategy Profile & Concept */}
            <div className="rounded-2xl border border-subtle bg-surface2/40 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-white">
                <Layers className="h-4 w-4 text-accent" />
                <span>Strategy Profile &amp; Core Concept</span>
              </div>
              <p className="text-gray-300 leading-relaxed font-medium">
                {spec.summary}
              </p>
            </div>

            {/* Execution Framework */}
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/10 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-emerald-400">
                <Compass className="h-4 w-4" />
                <span>Execution Framework</span>
              </div>
              <p className="text-gray-300 leading-relaxed">
                {spec.overview}
              </p>
            </div>

            {/* Risk & Portfolio Guardrails */}
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-950/10 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-indigo-400">
                <ShieldCheck className="h-4 w-4" />
                <span>Risk &amp; Portfolio Guardrails</span>
              </div>
              <p className="text-gray-300 leading-relaxed">
                {spec.riskProfile}
              </p>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
