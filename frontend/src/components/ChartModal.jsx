import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { CandleChart } from "./CandleChart";

function fmtNum(v) {
  return v == null ? "—" : v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// Centered overlay, same fixed/backdrop pattern as StrategyAnalyticsModal -- a chart wants width,
// not a narrow side panel. Zoom/pan preservation on live updates is handled inside CandleChart
// itself (series.update() vs setData(), see there) -- this component is presentation only.
export function ChartModal({ label, candles, price, change, changePct, onClose }) {
  const positive = (change ?? 0) >= 0;
  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
        onClick={onClose}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}
      >
        <motion.div
          className="flex h-[85vh] w-full max-w-6xl flex-col rounded-xl border border-subtle bg-surface p-4 shadow-2xl"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.97, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 12 }} transition={{ duration: 0.18, ease: "easeOut" }}
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-baseline gap-3">
              <h2 className="text-sm font-semibold">{label}</h2>
              <span className="text-xs text-faint">5m</span>
              <span className="font-mono text-lg font-semibold tabular-nums">{fmtNum(price)}</span>
              {change != null && (
                <span className={`font-mono text-xs font-medium tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
                  {positive ? "+" : ""}{fmtNum(change)} ({positive ? "+" : ""}{changePct}%)
                </span>
              )}
            </div>
            <button onClick={onClose} className="rounded p-1 text-faint hover:bg-surface3 hover:text-primary">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            {candles && candles.length > 0 ? (
              <CandleChart candles={candles} height="100%" />
            ) : (
              <div className="flex h-full items-center justify-center text-faint">No candle data yet</div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
