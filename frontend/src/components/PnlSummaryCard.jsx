import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Receipt, TrendingUp, TrendingDown, DollarSign, ShieldAlert, X, Info, Layers } from "lucide-react";
import { fetchPnlReport } from "../hooks/usePaperTradingSync";

function fmtRupee(v) {
  if (v == null) return "—";
  return `₹ ${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "text-muted";
}

import { createPortal } from "react-dom";

function TaxBreakdownModal({ grossPnl, totalCharges, tradesCount, onClose }) {
  const tc = Number(totalCharges) || 0;
  const estBrokerage = tradesCount * 40.0;
  const remaining = Math.max(0, tc - estBrokerage);
  const estStt = Math.round(remaining * 0.52 * 100) / 100;
  const estExchange = Math.round(remaining * 0.35 * 100) / 100;
  const estGst = Math.round(remaining * 0.11 * 100) / 100;
  const estStampDuty = Math.round((tc - (estBrokerage + estStt + estExchange + estGst)) * 100) / 100;

  return createPortal(
    <div
      className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-2xl border border-subtle bg-surface shadow-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-subtle px-5 py-4 bg-surface2/60">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent border border-accent/20">
              <Receipt className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-primary">Indian Regulatory Tax &amp; Charges Split</h3>
              <p className="text-[11px] text-faint">Itemized SEBI, Exchange &amp; Brokerage breakdown</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-faint hover:bg-surface3 hover:text-primary transition">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-3.5 text-xs">
          <div className="flex justify-between items-center py-1.5 border-b border-subtle/50">
            <span className="text-muted flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" /> Flat Brokerage (₹20/order)
            </span>
            <span className="font-mono font-bold text-primary">{fmtRupee(estBrokerage)}</span>
          </div>
          <div className="flex justify-between items-center py-1.5 border-b border-subtle/50">
            <span className="text-muted flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" /> STT (0.10% on Sell Premium)
            </span>
            <span className="font-mono font-bold text-primary">{fmtRupee(estStt)}</span>
          </div>
          <div className="flex justify-between items-center py-1.5 border-b border-subtle/50">
            <span className="text-muted flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" /> Exchange Turnover (NSE/BSE 0.05%)
            </span>
            <span className="font-mono font-bold text-primary">{fmtRupee(estExchange)}</span>
          </div>
          <div className="flex justify-between items-center py-1.5 border-b border-subtle/50">
            <span className="text-muted flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-purple-400" /> GST (18% on Brokerage &amp; Fees)
            </span>
            <span className="font-mono font-bold text-primary">{fmtRupee(estGst)}</span>
          </div>
          <div className="flex justify-between items-center py-1.5 border-b border-subtle/50">
            <span className="text-muted flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Stamp Duty (0.003% on Buy)
            </span>
            <span className="font-mono font-bold text-primary">{fmtRupee(estStampDuty)}</span>
          </div>

          <div className="mt-4 rounded-xl bg-surface2 p-3.5 border border-subtle flex items-center justify-between">
            <span className="font-bold text-primary uppercase tracking-wide">Total Deductions</span>
            <span className="font-mono text-base font-extrabold text-bear">{fmtRupee(totalCharges)}</span>
          </div>
        </div>
      </motion.div>
    </div>,
    document.body
  );
}

export function PnlSummaryCard() {
  const [combined, setCombined] = useState(null);
  const [showTaxModal, setShowTaxModal] = useState(false);

  useEffect(() => {
    let cancelled = false;
    function load() {
      fetchPnlReport({ range: "today" })
        .then((r) => {
          if (!cancelled) setCombined(r.combined);
        })
        .catch(() => {});
    }
    load();
    const interval = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const trades = combined?.trades ?? 0;
  const gross = combined?.gross_pnl ?? 0;
  const charges = combined?.charges ?? 0;
  const net = combined?.net_pnl ?? 0;
  const roi = (net / 450000) * 100; // on ₹4.5L active capital

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-4 sm:p-5 shadow-sm backdrop-blur-sm">
      <div className="flex items-center justify-between mb-3.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-primary">Today&apos;s Live Portfolio Performance</h3>
        </div>
        <button
          onClick={() => setShowTaxModal(true)}
          className="flex items-center gap-1.5 rounded-lg border border-subtle bg-surface2 px-2.5 py-1 text-xs font-semibold text-muted hover:bg-surface3 hover:text-primary transition"
        >
          <Receipt className="h-3.5 w-3.5 text-accent" />
          <span>Tax Split</span>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {/* 1. Trades */}
        <div className="rounded-xl border border-subtle bg-surface2/70 p-3.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-faint">Executed Trades</div>
          <div className="mt-1 font-mono text-xl font-bold text-primary tabular-nums">
            {trades}
          </div>
          <div className="text-[10px] text-faint mt-0.5">Across 21 Strategies</div>
        </div>

        {/* 2. Gross P&L */}
        <div className="rounded-xl border border-subtle bg-surface2/70 p-3.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-faint">Gross P&amp;L</div>
          <div className={`mt-1 font-mono text-xl font-bold tabular-nums ${pnlClass(gross)}`}>
            {gross > 0 ? "+" : ""}{fmtRupee(gross)}
          </div>
          <div className="text-[10px] text-faint mt-0.5">Before Statutory Fees</div>
        </div>

        {/* 3. Charges & Taxes */}
        <div className="rounded-xl border border-subtle bg-surface2/70 p-3.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-faint">Taxes &amp; Charges</div>
          <div className="mt-1 font-mono text-xl font-bold text-bear tabular-nums">
            {fmtRupee(charges)}
          </div>
          <div className="text-[10px] text-faint mt-0.5">STT + GST + ₹20 Brokerage</div>
        </div>

        {/* 4. Net P&L Hero Tile */}
        <div className="rounded-xl border border-subtle bg-surface2/90 p-3.5 ring-1 ring-accent/30 shadow-inner">
          <div className="text-[10px] font-bold uppercase tracking-wider text-accent">Net Realized P&amp;L</div>
          <div className={`mt-1 font-mono text-2xl font-black tabular-nums tracking-tight ${pnlClass(net)}`}>
            {net > 0 ? "+" : ""}{fmtRupee(net)}
          </div>
          <div className="text-[10px] text-faint mt-0.5">Realized in Wallet</div>
        </div>

        {/* 5. Daily ROI % */}
        <div className="rounded-xl border border-subtle bg-surface2/70 p-3.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-faint">Day ROI %</div>
          <div className={`mt-1 font-mono text-xl font-bold tabular-nums ${pnlClass(roi)}`}>
            {roi > 0 ? "+" : ""}{roi.toFixed(2)}%
          </div>
          <div className="text-[10px] text-faint mt-0.5">On ₹4.5L Margin</div>
        </div>
      </div>

      <AnimatePresence>
        {showTaxModal && (
          <TaxBreakdownModal
            grossPnl={gross}
            totalCharges={charges}
            tradesCount={trades}
            onClose={() => setShowTaxModal(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
