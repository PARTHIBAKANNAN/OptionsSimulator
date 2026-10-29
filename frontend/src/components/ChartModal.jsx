import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, TrendingUp, TrendingDown, Layers, Loader2 } from "lucide-react";
import { CandleChart } from "./CandleChart";
import { API_BASE } from "../lib/apiBase";

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
  bankniftyCandles = [],
  bankniftyPrice,
  bankniftyChange,
  bankniftyChangePct,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState(
    initialIndex?.includes("BANKNIFTY") ? "BANKNIFTY" : initialIndex?.includes("SENSEX") ? "SENSEX" : "NIFTY"
  );
  const [timeframe, setTimeframe] = useState("5m");
  const [customCandles, setCustomCandles] = useState(null);
  const [loadingTf, setLoadingTf] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadCandles() {
      try {
        setLoadingTf(true);
        const res = await fetch(`${API_BASE}/api/public/candles/${activeTab}?timeframe=${timeframe}&days=7`);
        const json = await res.json();
        if (active && Array.isArray(json.candles) && json.candles.length > 0) {
          setCustomCandles(json.candles);
        }
      } catch (err) {
        console.error("Failed to load candles:", err);
      } finally {
        if (active) setLoadingTf(false);
      }
    }
    loadCandles();
    return () => { active = false; };
  }, [activeTab, timeframe]);

  const streamCandles = activeTab === "BANKNIFTY" ? bankniftyCandles : activeTab === "SENSEX" ? sensexCandles : niftyCandles;
  const currentCandles = (customCandles && customCandles.length > 0) ? customCandles : streamCandles;

  const currentPrice = activeTab === "BANKNIFTY" ? bankniftyPrice : activeTab === "SENSEX" ? sensexPrice : niftyPrice;
  const currentChange = activeTab === "BANKNIFTY" ? bankniftyChange : activeTab === "SENSEX" ? sensexChange : niftyChange;
  const currentChangePct = activeTab === "BANKNIFTY" ? bankniftyChangePct : activeTab === "SENSEX" ? sensexChangePct : niftyChangePct;
  const positive = (currentChange ?? 0) >= 0;

  return createPortal(
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/85 p-0 sm:p-4 backdrop-blur-md"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
      >
        <motion.div
          className="flex h-[100dvh] sm:h-[95vh] w-full sm:w-[98vw] max-w-[98vw] flex-col rounded-none sm:rounded-3xl border-0 sm:border border-subtle bg-surface p-2 sm:p-5 shadow-2xl overflow-hidden pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.98, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.98, y: 15 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          {/* Top Control Header */}
          <div className="mb-2 sm:mb-3 flex flex-col gap-2 border-b border-subtle pb-2 sm:pb-3">
            {/* Row 1: Active Index & Price + Action Buttons */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                <span className="text-sm sm:text-base font-black text-primary truncate">
                  {activeTab}
                </span>

                <div className="flex items-baseline gap-1.5 sm:gap-2">
                  <span className="font-mono text-base sm:text-2xl font-black text-primary tabular-nums">
                    {fmtNum(currentPrice)}
                  </span>
                  {currentChange != null && (
                    <span className={`font-mono text-[11px] sm:text-xs font-bold tabular-nums flex items-center gap-0.5 ${positive ? "text-bull" : "text-bear"}`}>
                      {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                      {positive ? "+" : ""}{fmtNum(currentChange)} ({positive ? "+" : ""}{Number(currentChangePct).toFixed(2)}%)
                    </span>
                  )}
                </div>

                <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-bold text-cyan-400 border border-cyan-500/20">
                  <Layers className="h-3 w-3" />
                  EMA 20 • EMA 50 • VWAP • BB (20,2) • Vol+MA
                </span>
              </div>

              {/* Right: Close Button */}
              <div className="flex items-center shrink-0">
                <button
                  onClick={onClose}
                  className="rounded-xl p-2 text-faint hover:bg-surface2 hover:text-primary transition min-h-[44px] min-w-[44px] flex items-center justify-center"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Row 2: Selectors (Index tabs + Timeframe pills) - Wrap cleanly on mobile, 0 horizontal scroll */}
            <div className="flex flex-wrap items-center justify-between gap-1.5 sm:gap-2 py-0.5">
              {/* Index Switcher Tabs */}
              <div className="flex items-center gap-1 rounded-xl bg-surface2 p-0.5 sm:p-1 border border-subtle">
                {["NIFTY", "SENSEX", "BANKNIFTY"].map((idx) => (
                  <button
                    key={idx}
                    onClick={() => setActiveTab(idx)}
                    className={`rounded-lg px-2 sm:px-3 py-1 text-[11px] sm:text-xs font-bold transition ${
                      activeTab === idx ? "bg-accent text-white shadow-sm" : "text-faint hover:text-primary"
                    }`}
                  >
                    {idx === "NIFTY" ? "NIFTY 50" : idx}
                  </button>
                ))}
              </div>

              {/* Timeframe Switcher Tabs */}
              <div className="flex items-center gap-0.5 sm:gap-1 rounded-xl bg-surface2 p-0.5 sm:p-1 border border-subtle">
                {["1m", "3m", "5m", "15m", "1h", "1D"].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={`rounded-lg px-1.5 sm:px-2.5 py-1 text-[10px] sm:text-xs font-bold transition ${
                      timeframe === tf ? "bg-accent text-white shadow-sm" : "text-faint hover:text-primary"
                    }`}
                  >
                    {tf}
                  </button>
                ))}
                {loadingTf && <Loader2 className="h-3 w-3 animate-spin text-accent ml-0.5" />}
              </div>
            </div>
          </div>


          {/* Main Chart Canvas Area */}
          <div className="min-h-0 flex-1 relative">
            <div className="h-full">
              {currentCandles && currentCandles.length > 0 ? (
                <CandleChart candles={currentCandles} height="100%" />
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-faint gap-2">
                  <span>No candle data available for this session</span>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
