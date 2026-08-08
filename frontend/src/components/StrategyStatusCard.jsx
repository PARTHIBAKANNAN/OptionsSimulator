import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { StrategyAnalyticsModal } from "./StrategyAnalyticsModal";
import { approveSignal, closePosition, rejectSignal } from "../hooks/usePaperTradingSync";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
}

function pctReturn(entryPrice, otherPrice) {
  if (entryPrice == null || otherPrice == null || entryPrice === 0) return null;
  return ((otherPrice - entryPrice) / entryPrice) * 100;
}

function StatusDot({ entered }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${entered ? "bg-bull" : "bg-warn"}`} />;
}

// QuantMan-styled instrument row: contract/qty + BUY/SELL pills on the left, % return and P&L
// prominent on the right, SL/TP as a footer row.
function InstrumentPanel({ contract, qty, entryTime, entryPrice, ltp, pnl, stopLoss, takeProfit, exitTime }) {
  const pct = pctReturn(entryPrice, ltp);
  const closed = Boolean(exitTime);
  return (
    <div className="rounded-lg border border-subtle bg-surface2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono text-sm font-semibold">{contract}</div>
          {qty != null && <div className="text-xs text-faint">Qty: {qty}</div>}
          <div className="mt-2 flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5">
              <Badge variant="accent">BUY</Badge>
              <span className="font-mono tabular-nums">{fmtRupee(entryPrice)}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Badge variant={closed ? "bear" : "neutral"}>{closed ? "SELL" : "LTP"}</Badge>
              <span className="font-mono tabular-nums">{fmtRupee(ltp)}</span>
            </div>
          </div>
        </div>
        <div className="text-right">
          {pct != null && (
            <div className={`font-mono text-sm font-medium ${pnlClass(pct)}`}>
              {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
            </div>
          )}
          <div className={`font-mono text-xl font-bold tabular-nums ${pnlClass(pnl)}`}>
            {pnl != null && pnl >= 0 ? "+" : ""}{fmtRupee(pnl)}
          </div>
          <div className="mt-1 text-xs text-faint">{closed ? fmtTime(exitTime) : fmtTime(entryTime)}</div>
        </div>
      </div>
      <div className="mt-3 flex gap-4 border-t border-subtle pt-2 text-xs text-faint">
        <span>SL: <span className="font-mono text-bear">{fmtRupee(stopLoss)}</span></span>
        <span>TP: <span className="font-mono text-bull">{fmtRupee(takeProfit)}</span></span>
      </div>
    </div>
  );
}

function PendingSignalBanner({ signal }) {
  const [busy, setBusy] = useState(false);

  async function decide(action) {
    setBusy(true);
    try {
      await (action === "approve" ? approveSignal(signal.id) : rejectSignal(signal.id));
    } catch (e) {
      window.alert(e.message || "Action failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-accent/40 bg-accent/10 px-3 py-2">
      <div className="text-sm">
        <Badge variant={signal.direction === "CE" ? "bull" : "bear"}>{signal.contract ?? signal.strike}</Badge>{" "}
        <span className="text-muted">@ {fmtRupee(signal.entry_price)}</span>
      </div>
      <div className="flex gap-2">
        <button
          disabled={busy}
          className="rounded bg-bull px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          onClick={() => decide("approve")}
        >
          Approve
        </button>
        <button
          disabled={busy}
          className="rounded bg-bear px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          onClick={() => decide("reject")}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

function StrategyStatusRow({ row, pendingSignal }) {
  const [expanded, setExpanded] = useState(false);
  const [squaringOff, setSquaringOff] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const entered = row.status === "SIGNAL_ENTERED";
  const hasDetails = Boolean(row.entry || row.last_closed_today);

  async function handleSquareOff() {
    if (!row.entry?.order_id) return;
    if (!window.confirm(`Square off ${row.strategy}'s open position now?`)) return;
    setSquaringOff(true);
    try {
      await closePosition(row.entry.order_id);
    } catch (e) {
      window.alert(e.message || "Square off failed");
    } finally {
      setSquaringOff(false);
    }
  }

  return (
    <div className="border-t border-subtle py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-medium">{row.strategy}</span>
          <Badge variant="accent">Paper</Badge>
          <span className={`flex items-center gap-1.5 text-sm ${entered ? "text-bull" : "text-warn"}`}>
            <StatusDot entered={entered} />
            {entered ? "Signal Entered" : "Waiting for Entry Signal"}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-sm">
            <span className="text-faint">Today P&amp;L: </span>
            <span className={`font-mono font-medium tabular-nums ${pnlClass(row.today_pnl)}`}>{fmtRupee(row.today_pnl)}</span>
          </div>
          {hasDetails && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-muted hover:bg-surface3 hover:text-primary"
            >
              Details
              <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.15 }}>
                <ChevronDown className="h-3.5 w-3.5" />
              </motion.span>
            </button>
          )}
          {entered && (
            <button
              onClick={handleSquareOff}
              disabled={squaringOff}
              className="rounded border border-bear/40 px-2 py-1 text-xs font-medium text-bear hover:bg-bear/10 disabled:opacity-50"
            >
              {squaringOff ? "Squaring off…" : "Square Off"}
            </button>
          )}
          <button
            onClick={() => setShowAnalytics(true)}
            className="rounded bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90"
          >
            Show Strategy
          </button>
        </div>
      </div>

      {pendingSignal && <PendingSignalBanner signal={pendingSignal} />}

      <AnimatePresence initial={false}>
        {expanded && (row.entry || row.last_closed_today) && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-3">
              {row.entry ? (
                <InstrumentPanel
                  contract={row.entry.contract} qty={row.entry.qty} entryTime={row.entry.entry_time}
                  entryPrice={row.entry.entry_price} ltp={row.entry.ltp} pnl={row.entry.trade_pnl}
                  stopLoss={row.entry.stop_loss} takeProfit={row.entry.take_profit}
                />
              ) : (
                <InstrumentPanel
                  contract={row.last_closed_today.contract} qty={row.last_closed_today.qty}
                  entryTime={row.last_closed_today.entry_time} entryPrice={row.last_closed_today.entry_price}
                  ltp={row.last_closed_today.exit_price} pnl={row.last_closed_today.pnl}
                  stopLoss={row.last_closed_today.stop_loss} takeProfit={row.last_closed_today.take_profit}
                  exitTime={row.last_closed_today.exit_time}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {showAnalytics && <StrategyAnalyticsModal strategy={row.strategy} onClose={() => setShowAnalytics(false)} />}
    </div>
  );
}

export function StrategyStatusList({ strategies, pendingSignals = [] }) {
  return (
    <Card title={`Strategies (${strategies.length})`}>
      {strategies.length === 0 && <div className="py-3 text-center text-faint">No strategies loaded</div>}
      {strategies.map((row) => (
        <StrategyStatusRow
          key={row.strategy} row={row}
          pendingSignal={pendingSignals.find((s) => s.strategy === row.strategy)}
        />
      ))}
    </Card>
  );
}
