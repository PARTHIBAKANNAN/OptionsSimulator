import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronRight, Search, LayoutGrid, List, RotateCcw } from "lucide-react";
import { Badge } from "./ui/Badge";
import { StrategyAnalyticsModal } from "./StrategyAnalyticsModal";
import { approveSignal, closePosition, rejectSignal, restartStrategy } from "../hooks/usePaperTradingSync";

function fmtRupee(v) {
  if (v == null) return "—";
  return `₹ ${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "text-muted";
}

function pctReturn(entryPrice, otherPrice) {
  if (entryPrice == null || otherPrice == null || entryPrice === 0) return null;
  return ((otherPrice - entryPrice) / entryPrice) * 100;
}

// Ultra-premium animated radar beacon dot
function StatusBeacon({ entered }) {
  if (entered) {
    return (
      <span className="relative flex h-2.5 w-2.5 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bull opacity-75 duration-1000" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-bull shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
      </span>
    );
  }
  return (
    <span className="relative flex h-2.5 w-2.5 items-center justify-center">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-warn opacity-50 duration-1500" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-warn shadow-[0_0_6px_rgba(234,179,8,0.6)]" />
    </span>
  );
}

function parseStrategyMeta(name) {
  const isBankNifty = name.startsWith("BANKNIFTY");
  const isSensex = name.startsWith("SENSEX");
  const is5M = name.includes("_5M_");
  const isITM = name.includes("_ITM");
  const isCE = name.includes("_BULLISH") || name.includes("_SUPPORT_BOUNCE");

  return {
    index: isBankNifty ? "BANKNIFTY" : isSensex ? "SENSEX" : "NIFTY",
    tf: is5M ? "5M" : "1M",
    mode: isITM ? "ITM" : "ATM",
    dir: isCE ? "CE" : "PE",
  };
}

// Stepped TSL Animated Progress Gauge
function SteppedTslProgressGauge({ entryPrice, ltp, stopLoss, takeProfit, closed }) {
  if (entryPrice == null || ltp == null) return null;
  const deltaPts = ltp - entryPrice;
  const isProfit = deltaPts >= 0;

  // Compute active milestone state
  let currentStep = 0;
  let stepLabel = "Initial Hard SL (-20%)";
  let lockedPoints = 0;
  let nextMilestonePts = 20;

  if (deltaPts >= 80) {
    currentStep = 4;
    lockedPoints = deltaPts - 20;
    stepLabel = `Step 4: Dynamic Trailing (+${lockedPoints.toFixed(0)} pts)`;
    nextMilestonePts = takeProfit ? takeProfit - entryPrice : 150;
  } else if (deltaPts >= 60) {
    currentStep = 3;
    lockedPoints = 40;
    stepLabel = "Step 3: +40 pts Locked";
    nextMilestonePts = 80;
  } else if (deltaPts >= 40) {
    currentStep = 2;
    lockedPoints = 20;
    stepLabel = "Step 2: +20 pts Locked";
    nextMilestonePts = 60;
  } else if (deltaPts >= 20) {
    currentStep = 1;
    lockedPoints = 0;
    stepLabel = "Step 1: Cost Locked (Break-Even)";
    nextMilestonePts = 40;
  }

  const ptsToNext = Math.max(0, nextMilestonePts - deltaPts);
  const progressPct = Math.min(100, Math.max(5, (Math.max(0, deltaPts) / 100) * 100));

  return (
    <div className="mt-3 rounded-xl border border-subtle/80 bg-surface/80 p-2.5 font-mono text-xs">
      <div className="flex items-center justify-between text-[11px] mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="font-bold text-gray-400 font-sans">Stepped TSL:</span>
          <span className={`font-bold ${currentStep > 0 ? "text-emerald-400" : "text-amber-400"}`}>
            {closed ? "Position Closed" : stepLabel}
          </span>
        </div>
        <div className="font-bold text-accent">
          {deltaPts >= 0 ? `+${deltaPts.toFixed(1)}` : deltaPts.toFixed(1)} pts
        </div>
      </div>

      {/* Progress Track */}
      <div className="relative h-2 w-full rounded-full bg-surface3/80 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            currentStep >= 3
              ? "bg-gradient-to-r from-emerald-500 via-cyan-500 to-indigo-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"
              : currentStep >= 1
              ? "bg-gradient-to-r from-emerald-500 to-cyan-500"
              : isProfit
              ? "bg-emerald-500"
              : "bg-rose-500"
          }`}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Milestone Points */}
      <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400">
        <span className={currentStep >= 1 ? "text-emerald-400 font-bold" : ""}>+20pt (Cost)</span>
        <span className={currentStep >= 2 ? "text-emerald-400 font-bold" : ""}>+40pt (+20)</span>
        <span className={currentStep >= 3 ? "text-cyan-400 font-bold" : ""}>+60pt (+40)</span>
        <span className={currentStep >= 4 ? "text-indigo-400 font-bold" : ""}>+80pt+ (Trail)</span>
      </div>

      {!closed && ptsToNext > 0 && (
        <div className="mt-1.5 text-[10px] text-faint font-sans text-right">
          <span className="text-accent font-semibold">{ptsToNext.toFixed(1)} pts</span> to next profit lock
        </div>
      )}
    </div>
  );
}

// QuantMan exact instrument panel box
function QuantManInstrumentBox({ contract, qty, entryTime, entryPrice, ltp, pnl, stopLoss, takeProfit, exitTime }) {
  const pct = pctReturn(entryPrice, ltp);
  const closed = Boolean(exitTime);
  return (
    <div className="rounded-xl border border-subtle/80 bg-surface2/90 p-3.5 backdrop-blur-sm shadow-inner">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-sm font-bold tracking-wide text-primary">{contract}</div>
          <div className="text-xs text-faint mt-0.5">Qty : {qty ?? 65}</div>
        </div>
        <div className="text-right">
          {pct != null && (
            <div className={`font-mono text-xs font-bold ${pnlClass(pct)}`}>
              {pct >= 0 ? "" : ""}{pct.toFixed(1)}%
            </div>
          )}
          <div className={`font-mono text-base font-bold tabular-nums ${pnlClass(pnl)}`}>
            {pnl != null && pnl > 0 ? "" : ""}{fmtRupee(pnl)}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-subtle/60 pt-2.5 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-faint">Entry</span>
          <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] font-bold text-accent">BUY</span>
          <span className="font-mono font-semibold text-primary">{fmtRupee(entryPrice)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-faint">{closed ? "Exit" : "LTP"}</span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${closed ? "bg-bear/20 text-bear" : "bg-surface3 text-muted"}`}>
            {closed ? "SELL" : "LTP"}
          </span>
          <span className="font-mono font-semibold text-primary">{fmtRupee(ltp)}</span>
        </div>
      </div>

      {/* Stepped TSL Animated Progress Gauge */}
      <SteppedTslProgressGauge
        entryPrice={entryPrice}
        ltp={ltp}
        stopLoss={stopLoss}
        takeProfit={takeProfit}
        closed={closed}
      />
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
          className="rounded bg-bull px-3 py-1 text-xs font-medium text-white transition hover:brightness-110 disabled:opacity-50"
          onClick={() => decide("approve")}
        >
          Approve
        </button>
        <button
          disabled={busy}
          className="rounded bg-bear px-3 py-1 text-xs font-medium text-white transition hover:brightness-110 disabled:opacity-50"
          onClick={() => decide("reject")}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

// Strategy Card matching QuantMan UI Screenshot exactly
function StrategyCard({ row, pendingSignal }) {
  const [expanded, setExpanded] = useState(true);
  const [squaringOff, setSquaringOff] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);

  const entered = row.status === "SIGNAL_ENTERED";
  const hasDetails = Boolean(row.entry || row.last_closed);
  const meta = parseStrategyMeta(row.strategy);

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

  async function handleRestart() {
    setRestarting(true);
    try {
      await restartStrategy(row.strategy);
      window.alert(`${row.strategy} restarted for today's session.`);
    } catch (e) {
      window.alert(e.message || "Restart failed");
    } finally {
      setRestarting(false);
    }
  }

  return (
    <div className={`relative overflow-hidden rounded-2xl border border-subtle bg-surface p-4 transition-all duration-200 hover:border-border-strong ${entered ? "ring-1 ring-bull/40 shadow-lg" : "shadow-sm"}`}>
      {/* 1. Header Row (Chevron + Strategy Name + Badges) */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5">
          {hasDetails && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="mt-0.5 text-faint hover:text-primary transition"
              title="Toggle Details"
            >
              {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          )}
          <div>
            <h4 className="font-bold text-sm tracking-wide text-primary line-clamp-1" title={row.strategy}>
              {row.strategy}
            </h4>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span className="text-faint">Order type :</span>
              <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-[11px] font-bold text-cyan-400 border border-cyan-500/30">
                Paper
              </span>
              <div className="flex items-center gap-1.5 ml-1">
                <StatusBeacon entered={entered} />
                <span className={`text-xs font-semibold ${entered ? "text-bull" : "text-amber-400"}`}>
                  {entered ? "Signal Entered" : "Waiting for Next Entry Signal"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Index & TF Badges */}
        <div className="flex items-center gap-1">
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${meta.index === "NIFTY" ? "bg-cyan-500/15 text-cyan-400" : "bg-purple-500/15 text-purple-400"}`}>
            {meta.index}
          </span>
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-surface3 text-faint">
            {meta.tf}
          </span>
        </div>
      </div>

      {/* 2. Large P&L Amount & Inline Square Off Button */}
      <div className="mt-3 flex items-center justify-between">
        <div className={`font-mono text-2xl font-extrabold tabular-nums tracking-tight ${pnlClass(row.today_pnl)}`}>
          {row.today_pnl < 0 ? `- ₹ ${Math.abs(row.today_pnl).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : fmtRupee(row.today_pnl)}
        </div>

        {entered && (
          <button
            onClick={handleSquareOff}
            disabled={squaringOff}
            className="rounded-full border border-bear px-3.5 py-1 text-xs font-bold text-bear transition hover:bg-bear hover:text-white disabled:opacity-50"
          >
            {squaringOff ? "Closing…" : "Square off"}
          </button>
        )}
      </div>

      {/* 3. Collapsible / Visible Instrument Box */}
      <AnimatePresence initial={false}>
        {expanded && hasDetails && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden mt-3"
          >
            {row.entry ? (
              <QuantManInstrumentBox
                contract={row.entry.contract} qty={row.entry.qty} entryTime={row.entry.entry_time}
                entryPrice={row.entry.entry_price} ltp={row.entry.ltp} pnl={row.entry.trade_pnl}
                stopLoss={row.entry.stop_loss} takeProfit={row.entry.take_profit}
              />
            ) : (
              <QuantManInstrumentBox
                contract={row.last_closed.contract} qty={row.last_closed.qty}
                entryTime={row.last_closed.entry_time} entryPrice={row.last_closed.entry_price}
                ltp={row.last_closed.exit_price} pnl={row.last_closed.pnl}
                stopLoss={row.last_closed.stop_loss} takeProfit={row.last_closed.take_profit}
                exitTime={row.last_closed.exit_time}
              />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {pendingSignal && <PendingSignalBanner signal={pendingSignal} />}

      {/* 4. Action Buttons Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-subtle/50 pt-3">
        <button
          onClick={handleRestart}
          disabled={restarting}
          title="Restart strategy for today's session"
          className="flex items-center gap-1.5 rounded-lg border border-subtle bg-surface2 px-2.5 py-1.5 text-xs font-semibold text-muted transition hover:bg-surface3 hover:text-primary disabled:opacity-50"
        >
          <RotateCcw className={`h-3.5 w-3.5 ${restarting ? "animate-spin" : ""}`} />
          <span>Restart</span>
        </button>

        <button
          onClick={() => setShowAnalytics(true)}
          className="rounded-xl bg-accent px-4 py-1.5 text-xs font-bold text-white shadow-md transition hover:bg-accent/90"
        >
          Show Strategy
        </button>
      </div>

      {showAnalytics && <StrategyAnalyticsModal strategy={row.strategy} mode="live" onClose={() => setShowAnalytics(false)} />}
    </div>
  );
}

export function StrategyStatusList({ strategies = [], pendingSignals = [] }) {
  const [filterTab, setFilterTab] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState("grid");

  const filteredStrategies = useMemo(() => {
    return strategies.filter((s) => {
      const name = s.strategy;
      const isBankNifty = name.startsWith("BANKNIFTY");
      const isSensex = name.startsWith("SENSEX");
      const isNifty = !isBankNifty && !isSensex;
      const is5M = name.includes("_5M_");
      const isCE = name.includes("_BULLISH") || name.includes("_SUPPORT_BOUNCE");
      const isEntered = s.status === "SIGNAL_ENTERED";

      if (filterTab === "nifty" && !isNifty) return false;
      if (filterTab === "sensex" && !isSensex) return false;
      if (filterTab === "banknifty" && !isBankNifty) return false;
      if (filterTab === "5m" && !is5M) return false;
      if (filterTab === "1m" && is5M) return false;
      if (filterTab === "ce" && !isCE) return false;
      if (filterTab === "pe" && isCE) return false;
      if (filterTab === "active" && !isEntered) return false;

      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        return name.toLowerCase().includes(query);
      }
      return true;
    });
  }, [strategies, filterTab, searchTerm]);

  const niftyCount = strategies.filter((s) => s.strategy.startsWith("NIFTY")).length;
  const sensexCount = strategies.filter((s) => s.strategy.startsWith("SENSEX")).length;
  const bankNiftyCount = strategies.filter((s) => s.strategy.startsWith("BANKNIFTY")).length;
  const fiveMCount = strategies.filter((s) => s.strategy.includes("_5M_")).length;
  const oneMCount = strategies.filter((s) => !s.strategy.includes("_5M_")).length;

  return (
    <div className="space-y-4">
      {/* Header Controls & Filter Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-subtle bg-surface p-3.5 sm:p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => setFilterTab("all")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "all" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            All ({strategies.length})
          </button>
          <button
            onClick={() => setFilterTab("nifty")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "nifty" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            NIFTY ({niftyCount})
          </button>
          <button
            onClick={() => setFilterTab("sensex")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "sensex" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            SENSEX ({sensexCount})
          </button>
          <button
            onClick={() => setFilterTab("banknifty")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "banknifty" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            BANKNIFTY ({bankNiftyCount})
          </button>
          <button
            onClick={() => setFilterTab("5m")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "5m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            5M ITM ({fiveMCount})
          </button>
          <button
            onClick={() => setFilterTab("1m")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "1m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            1M ATM ({oneMCount})
          </button>
          <button
            onClick={() => setFilterTab("ce")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "ce" ? "bg-bull text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            Bullish (CE)
          </button>
          <button
            onClick={() => setFilterTab("pe")}
            className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterTab === "pe" ? "bg-bear text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            Bearish (PE)
          </button>
          {activeCount > 0 && (
            <button
              onClick={() => setFilterTab("active")}
              className={`rounded-xl px-3 py-1.5 text-xs font-bold flex items-center gap-1.5 transition ${filterTab === "active" ? "bg-bull text-white" : "bg-bull/15 text-bull border border-bull/30"}`}
            >
              <StatusBeacon entered={true} />
              In Trade ({activeCount})
            </button>
          )}
        </div>

        {/* Search & View Switcher */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 sm:w-60">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
            <input
              type="text"
              placeholder="Search strategies…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-xl border border-subtle bg-surface2 py-1.5 pl-8 pr-3 text-xs text-primary placeholder-faint focus:border-accent focus:outline-none"
            />
          </div>
          <div className="flex items-center rounded-xl border border-subtle bg-surface2 p-0.5">
            <button
              onClick={() => setViewMode("grid")}
              className={`rounded-lg p-1.5 text-xs transition ${viewMode === "grid" ? "bg-surface text-primary shadow-sm" : "text-faint hover:text-primary"}`}
              title="Grid View"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`rounded-lg p-1.5 text-xs transition ${viewMode === "list" ? "bg-surface text-primary shadow-sm" : "text-faint hover:text-primary"}`}
              title="List View"
            >
              <List className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Strategies List / Grid */}
      {filteredStrategies.length === 0 ? (
        <div className="rounded-2xl border border-subtle bg-surface py-12 text-center text-faint">
          No strategies match the selected filter.
        </div>
      ) : (
        <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4" : "space-y-3"}>
          {filteredStrategies.map((row) => (
            <StrategyCard
              key={row.strategy}
              row={row}
              pendingSignal={pendingSignals.find((s) => s.strategy === row.strategy)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
