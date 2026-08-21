import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { CandleChart } from "./CandleChart";

function fmtNum(v) {
  return v == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function ChartModal({ label, candles, price, change, changePct, onClose }) {
  const positive = (change ?? 0) >= 0;

  return createPortal(
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
      >
        <motion.div
          className="flex h-[85vh] w-full max-w-6xl flex-col rounded-2xl border border-subtle bg-surface p-5 shadow-2xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
          initial={{ opacity: 0, scale: 0.96, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 15 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          {/* Header */}
          <div className="mb-4 flex items-center justify-between border-b border-subtle pb-3">
            <div className="flex items-baseline gap-3">
              <h2 className="text-base font-bold text-primary">{label}</h2>
              <span className="rounded bg-accent/15 px-2 py-0.5 text-[11px] font-bold text-accent">5M Interval</span>
              <span className="font-mono text-xl font-bold tabular-nums text-primary">{fmtNum(price)}</span>
              {change != null && (
                <span className={`font-mono text-xs font-bold tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
                  {positive ? "+" : ""}{fmtNum(change)} ({positive ? "+" : ""}{Number(changePct).toFixed(2)}%)
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="rounded-xl p-1.5 text-faint hover:bg-surface2 hover:text-primary transition"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Chart View */}
          <div className="min-h-0 flex-1 relative">
            {candles && candles.length > 0 ? (
              <CandleChart candles={candles} height="100%" />
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-faint gap-2">
                <span>No candle data available for this session</span>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
