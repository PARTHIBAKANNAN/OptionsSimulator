import { useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Columns2, Square, TrendingUp, TrendingDown, Layers } from "lucide-react";
import { CandleChart } from "./CandleChart";

function fmtNum(v) {
  return v == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function ChartModal({
  initialIndex = "NIFTY",
  niftyCandles = [],
  niftyPrice,
  niftyChange,
  niftyChangePct,
  sensexCandles = [],
  sensexPrice,
  sensexChange,
  sensexChangePct,
  onClose,
}) {
  const [dualView, setDualView] = useState(false);
  const [activeTab, setActiveTab] = useState(initialIndex?.includes("SENSEX") ? "SENSEX" : "NIFTY");

  const isNiftyActive = activeTab === "NIFTY";
  const currentCandles = isNiftyActive ? niftyCandles : sensexCandles;
  const currentPrice = isNiftyActive ? niftyPrice : sensexPrice;
  const currentChange = isNiftyActive ? niftyChange : sensexChange;
  const currentChangePct = isNiftyActive ? niftyChangePct : sensexChangePct;
  const positive = (currentChange ?? 0) >= 0;

  return createPortal(
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/80 p-3 sm:p-5 backdrop-blur-md"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
      >
        <motion.div
          className="flex h-[90vh] w-full max-w-7xl flex-col rounded-3xl border border-subtle bg-surface p-4 sm:p-6 shadow-2xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.96, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 15 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          {/* Top Control Header */}
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-subtle pb-3">
            <div className="flex flex-wrap items-center gap-3">
              {/* Index Switcher Tabs */}
              <div className="flex items-center gap-1 rounded-xl bg-surface2 p-1 border border-subtle">
                <button
                  onClick={() => setActiveTab("NIFTY")}
                  className={`rounded-lg px-3.5 py-1 text-xs font-bold transition ${
                    isNiftyActive ? "bg-accent text-white shadow-sm" : "text-faint hover:text-primary"
                  }`}
                >
                  NIFTY 50
                </button>
                <button
                  onClick={() => setActiveTab("SENSEX")}
                  className={`rounded-lg px-3.5 py-1 text-xs font-bold transition ${
                    !isNiftyActive ? "bg-purple-600 text-white shadow-sm" : "text-faint hover:text-primary"
                  }`}
                >
                  SENSEX
                </button>
              </div>

              {/* Exact Price for Active Tab */}
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-xl sm:text-2xl font-black text-primary tabular-nums">
                  {fmtNum(currentPrice)}
                </span>
                {currentChange != null && (
                  <span className={`font-mono text-xs font-bold tabular-nums flex items-center gap-0.5 ${positive ? "text-bull" : "text-bear"}`}>
                    {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                    {positive ? "+" : ""}{fmtNum(currentChange)} ({positive ? "+" : ""}{Number(currentChangePct).toFixed(2)}%)
                  </span>
                )}
              </div>

              <span className="hidden md:inline-flex items-center gap-1 rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-bold text-cyan-400 border border-cyan-500/20">
                <Layers className="h-3 w-3" />
                EMA 20 (Cyan) • EMA 50 (Orange) • CVD Delta
              </span>
            </div>

            {/* Right: Dual View Toggle & Close */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setDualView(!dualView)}
                title={dualView ? "Switch to Single Chart" : "Switch to Side-by-Side Dual Charts"}
                className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition border ${
                  dualView
                    ? "border-accent/40 bg-accent/15 text-accent shadow-sm"
                    : "border-subtle bg-surface2 text-faint hover:text-primary"
                }`}
              >
                {dualView ? <Square className="h-3.5 w-3.5" /> : <Columns2 className="h-3.5 w-3.5" />}
                <span className="hidden sm:inline">{dualView ? "Single View" : "Split Dual View"}</span>
              </button>

              <button
                onClick={onClose}
                className="rounded-xl p-1.5 text-faint hover:bg-surface2 hover:text-primary transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Main Chart Canvas Area */}
          <div className="min-h-0 flex-1 relative">
            {dualView ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
                {/* Left Chart (NIFTY) */}
                <div className="flex flex-col h-full rounded-2xl border border-subtle/80 bg-surface2/30 p-2 overflow-hidden">
                  <div className="flex items-center justify-between px-2 py-1 mb-1">
                    <span className="font-bold text-xs text-cyan-400">NIFTY 50 (5M)</span>
                    <span className="font-mono text-xs font-bold text-primary">{fmtNum(niftyPrice)}</span>
                  </div>
                  <div className="flex-1 min-h-0">
                    <CandleChart candles={niftyCandles} height="100%" />
                  </div>
                </div>

                {/* Right Chart (SENSEX) */}
                <div className="flex flex-col h-full rounded-2xl border border-subtle/80 bg-surface2/30 p-2 overflow-hidden">
                  <div className="flex items-center justify-between px-2 py-1 mb-1">
                    <span className="font-bold text-xs text-purple-400">SENSEX (5M)</span>
                    <span className="font-mono text-xs font-bold text-primary">{fmtNum(sensexPrice)}</span>
                  </div>
                  <div className="flex-1 min-h-0">
                    <CandleChart candles={sensexCandles} height="100%" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full">
                {currentCandles && currentCandles.length > 0 ? (
                  <CandleChart candles={currentCandles} height="100%" />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-faint gap-2">
                    <span>No candle data available for this session</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
