import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Layers, Cpu, Compass, ShieldCheck, Target, Clock, ArrowUpRight, ArrowDownRight, Activity } from "lucide-react";

const STRATEGY_SPECS = {
  // NIFTY 5M ITM
  NIFTY_ORB_BULLISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "ITM (+1 / +2 Strike CE, Δ ≈ 0.60)",
    targetPremium: "₹200 Target Premium",
    indicators: [
      { name: "Opening Range (09:15 - 09:30 IST)", formula: "High_ORB = max(High[09:15..09:25]), Low_ORB = min(Low[09:15..09:25])" },
      { name: "1H 50-EMA Macro Trend Filter", formula: "EMA_50_1H = EMA(Close_1H, span=50)" },
      { name: "5M 20-EMA & 50-EMA Confluence", formula: "EMA_20_5M > EMA_50_5M (Bullish Stack)" },
      { name: "Tick Cumulative Volume Delta (CVD)", formula: "CVD > 0 (Aggressive buyers dominant)" },
    ],
    entryLogic: "At or after 09:30 IST, candle closes above High_ORB with Close > EMA_50_1H and positive volume expansion. Single-bar crossover trigger prevents duplicate fills.",
    exitRules: {
      steppedTsl: "+20 pt gain → Lock Break-Even; +40 pt gain → Lock +20 pt; +60 pt gain → Lock +40 pt",
      stopLoss: "20% of entry option premium (Max risk ~₹2,600 / lot)",
      targetProfit: "+50 option points (+25% gain, ~₹3,250 / lot)",
      timeExit: "90 - 120 minutes max hold time (prevents afternoon theta decay)",
    },
  },
  NIFTY_ORB_BEARISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "ITM (+1 / +2 Strike PE, Δ ≈ 0.60)",
    targetPremium: "₹200 Target Premium",
    indicators: [
      { name: "Opening Range (09:15 - 09:30 IST)", formula: "High_ORB = max(High[09:15..09:25]), Low_ORB = min(Low[09:15..09:25])" },
      { name: "1H 50-EMA Macro Trend Filter", formula: "EMA_50_1H = EMA(Close_1H, span=50)" },
      { name: "5M 20-EMA & 50-EMA Confluence", formula: "EMA_20_5M < EMA_50_5M (Bearish Stack)" },
      { name: "Tick Cumulative Volume Delta (CVD)", formula: "CVD < 0 (Aggressive sellers dominant)" },
    ],
    entryLogic: "At or after 09:30 IST, candle closes below Low_ORB with Close < EMA_50_1H and expanding negative volume delta. Single-bar crossover trigger prevents duplicate fills.",
    exitRules: {
      steppedTsl: "+20 pt gain → Lock Break-Even; +40 pt gain → Lock +20 pt; +60 pt gain → Lock +40 pt",
      stopLoss: "20% of entry option premium (Max risk ~₹2,600 / lot)",
      targetProfit: "+50 option points (+25% gain, ~₹3,250 / lot)",
      timeExit: "90 - 120 minutes max hold time",
    },
  },
  NIFTY_EMA_BOUNCE_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "ITM (+1 Strike CE, Δ ≈ 0.60)",
    targetPremium: "₹200 Target Premium",
    indicators: [
      { name: "20-EMA Dynamic Support", formula: "EMA_20 = Close * (2/21) + EMA_prev * (19/21)" },
      { name: "RSI Momentum Filter", formula: "RSI(14) between 45 and 65 (Healthy pullbacks)" },
      { name: "Price Action Reversal", formula: "Low <= EMA_20 and Close > EMA_20 and Close > Open" },
    ],
    entryLogic: "5M candle tests the rising 20-EMA from above, forms a bullish hammer/rejection wick, and closes firmly above EMA_20 with RSI > 50.",
    exitRules: {
      steppedTsl: "+20 pt gain → Lock Break-Even; +40 pt gain → Lock +20 pt",
      stopLoss: "20% of entry premium or 5M swing low break",
      targetProfit: "+50 option points",
      timeExit: "90 minutes max holding period",
    },
  },
  NIFTY_EMA_REJECTION_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "ITM (+1 Strike PE, Δ ≈ 0.60)",
    targetPremium: "₹200 Target Premium",
    indicators: [
      { name: "20-EMA Dynamic Resistance", formula: "EMA_20 = Close * (2/21) + EMA_prev * (19/21)" },
      { name: "RSI Momentum Filter", formula: "RSI(14) < 50 (Bearish momentum)" },
      { name: "Price Action Reversal", formula: "High >= EMA_20 and Close < EMA_20 and Close < Open" },
    ],
    entryLogic: "5M candle rallies into a downward-sloping 20-EMA, forms an upper rejection wick, and closes below EMA_20.",
    exitRules: {
      steppedTsl: "+20 pt gain → Lock Break-Even; +40 pt gain → Lock +20 pt",
      stopLoss: "20% of entry premium",
      targetProfit: "+50 option points",
      timeExit: "90 minutes max holding period",
    },
  },
  NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "ITM (+1 Strike CE, Δ ≈ 0.60)",
    targetPremium: "₹200 Target Premium",
    indicators: [
      { name: "Heikin-Ashi Smoothing", formula: "Close_HA = (O+H+L+C)/4, Open_HA = (Open_HA_prev + Close_HA_prev)/2" },
      { name: "Flat-Bottom Signal", formula: "Low_HA == Open_HA (Zero lower shadow = intense buying)" },
    ],
    entryLogic: "Two consecutive green Heikin-Ashi candles with flat bottoms (no lower shadows) above 20-EMA.",
    exitRules: {
      steppedTsl: "+20 pt gain → Lock Break-Even; +40 pt gain → Lock +20 pt",
      stopLoss: "20% of entry premium",
      targetProfit: "+50 option points",
      timeExit: "90 minutes",
    },
  },
  NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM: {
    timeframe: "5-Minute",
    index: "NSE NIFTY 50 (Lot Size: 65)",
    strikeMode: "ITM (+1 Strike PE, Δ ≈ 0.60)",
    targetPremium: "₹200 Target Premium",
    indicators: [
      { name: "Heikin-Ashi Smoothing", formula: "Close_HA = (O+H+L+C)/4, Open_HA = (Open_HA_prev + Close_HA_prev)/2" },
      { name: "Flat-Top Signal", formula: "High_HA == Open_HA (Zero upper shadow = intense selling)" },
    ],
    entryLogic: "Two consecutive red Heikin-Ashi candles with flat tops (no upper shadows) below 20-EMA.",
    exitRules: {
      steppedTsl: "+20 pt gain → Lock Break-Even; +40 pt gain → Lock +20 pt",
      stopLoss: "20% of entry premium",
      targetProfit: "+50 option points",
      timeExit: "90 minutes",
    },
  },
  // Default Template for SENSEX & ATM strategies
  DEFAULT: {
    timeframe: "5-Minute / 1-Minute",
    index: "Index Derivatives (NIFTY 65 / SENSEX 20)",
    strikeMode: "Delta-Optimized (Δ ≈ 0.60 ITM / ATM)",
    targetPremium: "Dynamic Greeks Targeting",
    indicators: [
      { name: "Exponential Moving Averages", formula: "EMA(20) & EMA(50) Trend Alignment" },
      { name: "MACD Momentum Engine", formula: "MACD(12,26,9) Histogram Sign Flip" },
      { name: "Volume & Delta Filter", formula: "Tick Cumulative Volume Delta (CVD) Confirmation" },
    ],
    entryLogic: "Systematic multi-timeframe signal validation with strict cooldown deduplication.",
    exitRules: {
      steppedTsl: "+20 pt / +30 pt Stepped Ratchet Profit Locks",
      stopLoss: "20% Hard Risk Guardrail",
      targetProfit: "+50 option points target",
      timeExit: "90 - 120 minutes maximum holding period",
    },
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
          className="flex h-[88vh] w-full max-w-4xl flex-col rounded-3xl border border-subtle bg-surface p-5 sm:p-7 shadow-2xl overflow-y-auto"
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
              <h2 className="text-lg sm:text-xl font-black text-white tracking-tight">{name}</h2>
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
          <div className="space-y-5 text-xs font-sans leading-relaxed">
            {/* Mathematical Indicators Section */}
            <div className="rounded-2xl border border-subtle bg-surface2/40 p-4 space-y-3">
              <div className="flex items-center gap-2 font-bold text-sm text-white">
                <Cpu className="h-4 w-4 text-accent" />
                <span>Quantitative Indicator Calculations</span>
              </div>
              <div className="space-y-2">
                {spec.indicators.map((ind, idx) => (
                  <div key={idx} className="rounded-xl bg-surface p-3 border border-subtle/80 font-mono">
                    <div className="text-[11px] font-bold text-accent mb-1 font-sans">{ind.name}</div>
                    <div className="text-xs text-gray-300 bg-surface2/60 px-2.5 py-1.5 rounded-lg border border-subtle/40 overflow-x-auto">
                      <code>{ind.formula}</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Entry Condition */}
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/10 p-4 space-y-2">
              <div className="flex items-center gap-2 font-bold text-sm text-emerald-400">
                <Compass className="h-4 w-4" />
                <span>Exact Order Entry Condition</span>
              </div>
              <p className="text-gray-300 text-xs leading-relaxed">
                {spec.entryLogic}
              </p>
            </div>

            {/* Exit & Risk Rule Set */}
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-950/10 p-4 space-y-3">
              <div className="flex items-center gap-2 font-bold text-sm text-indigo-400">
                <ShieldCheck className="h-4 w-4" />
                <span>Stepped TSL &amp; Risk Guardrails</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-[11px]">
                <div className="p-3 rounded-xl bg-surface border border-subtle/80">
                  <span className="text-gray-400 text-[10px] uppercase block font-sans">Stepped Ratchet TSL</span>
                  <span className="text-emerald-400 font-bold">{spec.exitRules.steppedTsl}</span>
                </div>
                <div className="p-3 rounded-xl bg-surface border border-subtle/80">
                  <span className="text-gray-400 text-[10px] uppercase block font-sans">Stop Loss Guardrail</span>
                  <span className="text-rose-400 font-bold">{spec.exitRules.stopLoss}</span>
                </div>
                <div className="p-3 rounded-xl bg-surface border border-subtle/80">
                  <span className="text-gray-400 text-[10px] uppercase block font-sans">Take Profit Target</span>
                  <span className="text-cyan-400 font-bold">{spec.exitRules.targetProfit}</span>
                </div>
                <div className="p-3 rounded-xl bg-surface border border-subtle/80">
                  <span className="text-gray-400 text-[10px] uppercase block font-sans">Holding Limit (Time Exit)</span>
                  <span className="text-amber-400 font-bold">{spec.exitRules.timeExit}</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
