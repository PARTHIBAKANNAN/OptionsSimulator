import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, ShieldCheck } from "lucide-react";

export function ExposureMeter({ positions = [] }) {
  const cePositions = positions.filter((p) => (p.symbol || p.contract || "").endsWith("CE"));
  const pePositions = positions.filter((p) => (p.symbol || p.contract || "").endsWith("PE"));

  const totalActive = positions.length;
  const cePercent = totalActive ? Math.round((cePositions.length / totalActive) * 100) : 50;
  const pePercent = totalActive ? Math.round((pePositions.length / totalActive) * 100) : 50;

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-4 shadow-sm backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent border border-accent/20">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-primary">Directional Bias &amp; Exposure</h4>
            <p className="text-[11px] text-faint">Live portfolio directional balance across all 21 strategies</p>
          </div>
        </div>
        <div className="text-right">
          <span className="text-xs font-bold text-primary">{totalActive} Active Positions</span>
        </div>
      </div>

      {/* Exposure Split Progress Bar */}
      <div className="mt-3">
        <div className="flex justify-between text-xs font-bold mb-1.5">
          <span className="flex items-center gap-1 text-bull">
            <TrendingUp className="h-3.5 w-3.5" /> Bullish (CE): {cePercent}% ({cePositions.length})
          </span>
          <span className="flex items-center gap-1 text-bear">
            Bearish (PE): {pePercent}% ({pePositions.length}) <TrendingDown className="h-3.5 w-3.5" />
          </span>
        </div>

        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-surface3 flex">
          <motion.div
            initial={{ width: "50%" }}
            animate={{ width: `${cePercent}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="h-full bg-gradient-to-r from-emerald-500 to-teal-400"
          />
          <motion.div
            initial={{ width: "50%" }}
            animate={{ width: `${pePercent}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="h-full bg-gradient-to-r from-rose-500 to-red-600"
          />
        </div>
      </div>
    </div>
  );
}
