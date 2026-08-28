import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Layers, Cpu, Compass, ShieldCheck, ArrowUpRight, ArrowDownRight } from "lucide-react";

const STRATEGY_SPECS = {
  NIFTY_ORB_BULLISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Call",
    profile: "Opening Breakout Alpha",
    summary: "Captures morning opening range momentum following initial price discovery, filtering false breakouts with higher-timeframe trend alignment.",
    overview: "Monitors opening volatility across primary index constituents to identify high-conviction breakout opportunities. Uses adaptive trailing risk rules to lock in profits during rapid momentum expansions.",
    riskProfile: "Fixed percentage risk guardrail with multi-tiered stepped trailing profit ratchet.",
  },
  NIFTY_ORB_BEARISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Put",
    profile: "Opening Breakdown Alpha",
    summary: "Executes directional downside breakdowns when opening order flow velocity indicates aggressive institutional distribution.",
    overview: "Identifies early session breakdown patterns below key price levels, riding downside momentum while enforcing strict time-based exit limits.",
    riskProfile: "Fixed percentage risk guardrail with multi-tiered stepped trailing profit ratchet.",
  },
  NIFTY_EMA_BOUNCE_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Call",
    profile: "Trend Continuation Pullback",
    summary: "Enters high-probability pullback entries testing institutional dynamic support levels during established uptrends.",
    overview: "Capitalizes on short-term price pullbacks within stronger macro uptrends. Trades mean-reversion bounces back toward dominant trend direction.",
    riskProfile: "Automated trailing profit ratchet with defined stop loss protection.",
  },
  NIFTY_EMA_REJECTION_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "Delta-Optimized ITM Put",
    profile: "Trend Continuation Rejection",
    summary: "Capitalizes on overhead resistance rejections aligned with primary downward trend momentum.",
    overview: "Systematically executes downside position entries when relief rallies fail at key dynamic resistance zones.",
    riskProfile: "Automated trailing profit ratchet with defined stop loss protection.",
  },
  DEFAULT: {
    timeframe: "5-Minute / 1-Minute",
    index: "Index Derivatives (NIFTY / SENSEX / BANKNIFTY)",
    strikeMode: "Delta-Optimized Options",
    profile: "Systematic Quantitative Model",
    summary: "Systematic non-discretionary algorithmic execution model engineered for Indian index options microstructure.",
    overview: "Evaluates multi-timeframe price discovery, momentum alignment, and structural volatility parameters to execute disciplined directional trades.",
    riskProfile: "Standard institutional risk parameters including stop loss limits, stepped profit locks, and time-decay holding caps.",
  },
};

export function StrategyDetailModal({ strategy, onClose }) {
  if (!strategy) return null;

  const name = typeof strategy === "string" ? strategy : strategy.name || strategy.strategy || "STRATEGY";
  const spec = STRATEGY_SPECS[name] || STRATEGY_SPECS.DEFAULT;
  const isCE = name.includes("BULLISH") || name.includes("CE") || name.includes("BOUNCE");

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
          className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-3xl border border-subtle bg-surface p-5 sm:p-7 shadow-2xl overflow-y-auto"
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

          {/* Executive Overview Content (Zero internal math leaks) */}
          <div className="space-y-4 text-xs font-sans leading-relaxed">
            <div className="rounded-2xl border border-subtle bg-surface2/40 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-white">
                <Layers className="h-4 w-4 text-accent" />
                <span>Strategy Profile &amp; Core Concept</span>
              </div>
              <p className="text-gray-300 leading-relaxed font-medium">
                {spec.summary}
              </p>
            </div>

            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/10 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-emerald-400">
                <Compass className="h-4 w-4" />
                <span>Execution Framework</span>
              </div>
              <p className="text-gray-300 leading-relaxed">
                {spec.overview}
              </p>
            </div>

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
