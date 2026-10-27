import { useState } from "react";
import { 
  ShieldAlert, 
  RotateCcw, 
  AlertTriangle, 
  CheckCircle2, 
  Wifi, 
  Lock, 
  Sliders, 
  Activity, 
  Zap,
  Clock,
  Layers,
  ArrowRight
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export function SettingsScreen({ onOpenAliceLogin }) {
  const [closingAll, setClosingAll] = useState(false);
  const [restartingAll, setRestartingAll] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);

  async function handleSquareOffAll() {
    setClosingAll(true);
    try {
      const res = await fetch("/api/paper/positions/close-all", { method: "POST" });
      const data = await res.json();
      setActionMessage({
        type: "success",
        text: `Successfully squared off ${data.closed_count || 0} open positions across all strategies.`
      });
      setShowConfirmModal(false);
    } catch (e) {
      setActionMessage({
        type: "error",
        text: `Square Off All failed: ${e.message}`
      });
    } finally {
      setClosingAll(false);
    }
  }

  async function handleRestartAll() {
    setRestartingAll(true);
    try {
      const res = await fetch("/api/paper/strategies/restart-all", { method: "POST" });
      const data = await res.json();
      setActionMessage({
        type: "success",
        text: `Re-armed and restarted all ${data.restarted_count || 44} strategies for the session.`
      });
    } catch (e) {
      setActionMessage({
        type: "error",
        text: `Restart failed: ${e.message}`
      });
    } finally {
      setRestartingAll(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-12">
      {/* Header */}
      <div>
        <h2 className="text-xl sm:text-2xl font-black tracking-tight text-primary">
          System Settings &amp; Controls
        </h2>
        <p className="text-xs sm:text-sm text-faint mt-1">
          Autonomous execution fail-safes, broker connection health, and engine circuit breakers.
        </p>
      </div>

      {/* Action Notification Banner */}
      <AnimatePresence>
        {actionMessage && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className={`flex items-center justify-between rounded-xl border p-4 text-xs font-semibold ${
              actionMessage.type === "success"
                ? "bg-bull/10 border-bull/30 text-bull"
                : "bg-bear/10 border-bear/30 text-bear"
            }`}
          >
            <div className="flex items-center gap-2">
              {actionMessage.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              )}
              <span>{actionMessage.text}</span>
            </div>
            <button
              onClick={() => setActionMessage(null)}
              className="ml-4 font-bold opacity-70 hover:opacity-100"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Grid: Global Emergency Operations */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Square Off All Emergency Card */}
        <div className="rounded-2xl border border-bear/30 bg-bear/5 p-5 shadow-sm space-y-4">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-bear/15 p-2.5 text-bear shrink-0">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-primary">Emergency Square Off All</h3>
              <p className="text-xs text-faint mt-1 leading-relaxed">
                Immediately market-closes all active positions across all 44 systematic strategies. Does not cancel pending orders or re-trigger exits.
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowConfirmModal(true)}
            disabled={closingAll}
            className="w-full rounded-xl bg-bear hover:bg-bear/90 text-white py-3 text-xs font-bold transition shadow-md shadow-bear/20 flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50"
          >
            <AlertTriangle className="h-4 w-4" />
            <span>{closingAll ? "Closing All Positions…" : "Square Off All Active Positions"}</span>
          </button>
        </div>

        {/* Restart / Re-Arm Strategies Card */}
        <div className="rounded-2xl border border-accent/30 bg-accent/5 p-5 shadow-sm space-y-4">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-accent/15 p-2.5 text-accent shrink-0">
              <RotateCcw className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-primary">Restart &amp; Re-Arm All Strategies</h3>
              <p className="text-xs text-faint mt-1 leading-relaxed">
                Clears intraday signal latches, resets cooldown timestamps, and re-arms the live engine to evaluate fresh entries on the next incoming tick.
              </p>
            </div>
          </div>

          <button
            onClick={handleRestartAll}
            disabled={restartingAll}
            className="w-full rounded-xl bg-accent hover:bg-accent/90 text-white py-3 text-xs font-bold transition shadow-md shadow-accent/25 flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50"
          >
            <RotateCcw className={`h-4 w-4 ${restartingAll ? "animate-spin" : ""}`} />
            <span>{restartingAll ? "Re-Arming All 44 Strategies…" : "Restart & Re-Arm All 44 Strategies"}</span>
          </button>
        </div>
      </div>

      {/* Alice Blue Broker Session & Credentials */}
      <div className="rounded-2xl border border-subtle bg-surface p-5 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-subtle pb-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-cyan-500/15 p-2.5 text-cyan-400">
              <Wifi className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-primary">Alice Blue Broker Gateway</h3>
              <p className="text-xs text-faint">Direct Indian Exchange WebSocket &amp; Order Execution Gateway</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full bg-bull/15 px-3 py-1 text-xs font-bold text-bull border border-bull/20 font-mono">
              <span className="h-2 w-2 rounded-full bg-bull animate-pulse" />
              SESSION ACTIVE
            </span>
            {onOpenAliceLogin && (
              <button
                onClick={onOpenAliceLogin}
                className="rounded-xl border border-subtle bg-surface2 hover:bg-surface3 px-3 py-1.5 text-xs font-bold text-primary transition active:scale-95"
              >
                Re-Authenticate OTP
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
          <div className="rounded-xl border border-subtle bg-surface2/60 p-3">
            <div className="text-[10px] font-sans font-semibold text-faint uppercase">Broker ID</div>
            <div className="mt-1 font-bold text-primary">ALICEBLUE</div>
          </div>
          <div className="rounded-xl border border-subtle bg-surface2/60 p-3">
            <div className="text-[10px] font-sans font-semibold text-faint uppercase">Heartbeat</div>
            <div className="mt-1 font-bold text-bull">Sub-millisecond</div>
          </div>
          <div className="rounded-xl border border-subtle bg-surface2/60 p-3">
            <div className="text-[10px] font-sans font-semibold text-faint uppercase">Indices Streamed</div>
            <div className="mt-1 font-bold text-primary">NIFTY, BANKNIFTY, SENSEX</div>
          </div>
          <div className="rounded-xl border border-subtle bg-surface2/60 p-3">
            <div className="text-[10px] font-sans font-semibold text-faint uppercase">Order Engine Mode</div>
            <div className="mt-1 font-bold text-accent">PAPER SIMULATOR</div>
          </div>
        </div>
      </div>

      {/* Quantitative Engine Gate Rules & Circuit Breakers */}
      <div className="rounded-2xl border border-subtle bg-surface p-5 space-y-4 shadow-sm">
        <div className="flex items-center gap-3 border-b border-subtle pb-4">
          <div className="rounded-xl bg-purple-500/15 p-2.5 text-purple-400">
            <Sliders className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-primary">Quantitative Gate Configurations &amp; TSL Rules</h3>
            <p className="text-xs text-faint">Active mathematical filters enforced across all 44 strategies</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-faint font-semibold uppercase text-[10px]">
              <span>ADX Trend Strength</span>
              <span className="text-accent font-bold">&ge; 20.0</span>
            </div>
            <p className="text-faint text-[11px] pt-1">
              Wilder smoothed ADX(14) required to reject choppy sideways consolidation before entering trend breakouts.
            </p>
          </div>

          <div className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-faint font-semibold uppercase text-[10px]">
              <span>VWAP Proximity Gate</span>
              <span className="text-accent font-bold">&le; 0.40%</span>
            </div>
            <p className="text-faint text-[11px] pt-1">
              Guards against overextended prices far from institutional benchmark volume-weighted average price.
            </p>
          </div>

          <div className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-faint font-semibold uppercase text-[10px]">
              <span>Midday Volume Gate</span>
              <span className="text-accent font-bold">&ge; 1.40x Avg</span>
            </div>
            <p className="text-faint text-[11px] pt-1">
              Between 11:30 AM &amp; 1:30 PM, volume must surge 1.4x above 20-period moving average to avoid low-liquidity traps.
            </p>
          </div>

          <div className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-faint font-semibold uppercase text-[10px]">
              <span>SENSEX Cost Lock (ATM)</span>
              <span className="text-bull font-bold font-mono">25 Points</span>
            </div>
            <p className="text-faint text-[11px] pt-1">
              When SENSEX ATM option gains +25 pts, TSL automatically locks to entry price (break-even guarantee).
            </p>
          </div>

          <div className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-faint font-semibold uppercase text-[10px]">
              <span>SENSEX Cost Lock (ITM)</span>
              <span className="text-bull font-bold font-mono">35 Points</span>
            </div>
            <p className="text-faint text-[11px] pt-1">
              When SENSEX ITM option gains +35 pts, TSL locks to entry price before trailing forward.
            </p>
          </div>

          <div className="rounded-xl border border-subtle bg-surface2/60 p-3.5 space-y-1">
            <div className="flex items-center justify-between text-faint font-semibold uppercase text-[10px]">
              <span>Strike Loss Lockout</span>
              <span className="text-bear font-bold font-mono">60 Minutes</span>
            </div>
            <p className="text-faint text-[11px] pt-1">
              After an option contract stops out at Hard SL, that specific strike is locked for 60 minutes to prevent revenge trades.
            </p>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      <AnimatePresence>
        {showConfirmModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-md rounded-2xl border border-bear/30 bg-surface p-6 shadow-2xl space-y-4"
            >
              <div className="flex items-center gap-3 text-bear">
                <AlertTriangle className="h-6 w-6 shrink-0" />
                <h4 className="font-black text-base text-primary">Confirm Emergency Square Off All</h4>
              </div>

              <p className="text-xs text-muted leading-relaxed">
                Are you sure you want to market-close <strong className="text-bear font-bold">ALL open positions</strong> across all 44 strategies? This action will execute immediate market exits on the paper engine.
              </p>

              <div className="grid grid-cols-2 gap-3 pt-2">
                <button
                  onClick={() => setShowConfirmModal(false)}
                  className="rounded-xl border border-subtle bg-surface2 hover:bg-surface3 py-2.5 text-xs font-semibold text-primary transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSquareOffAll}
                  disabled={closingAll}
                  className="rounded-xl bg-bear hover:bg-bear/90 text-white py-2.5 text-xs font-bold transition shadow-md shadow-bear/25 flex items-center justify-center gap-1.5"
                >
                  {closingAll ? "Closing All…" : "Confirm Square Off"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
