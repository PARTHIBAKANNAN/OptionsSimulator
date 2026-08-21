import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Search, LayoutGrid, List } from "lucide-react";
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
      <span className="relative flex h-3 w-3 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bull opacity-75 duration-1000" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-bull shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
      </span>
    );
  }
  return (
    <span className="relative flex h-3 w-3 items-center justify-center">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-warn opacity-50 duration-1500" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-warn shadow-[0_0_6px_rgba(234,179,8,0.6)]" />
    </span>
  );
}

function parseStrategyMeta(name) {
  const isSensex = name.startsWith("SENSEX");
  const is5M = name.includes("_5M_");
  const isITM = name.includes("_ITM");
  const isCE = name.includes("_BULLISH") || name.includes("_SUPPORT_BOUNCE");

  const cleanName = name
    .replace(/^NIFTY_|^SENSEX_/, "")
    .replace(/_1M_ATM|_5M_ITM|_1M|_5M/, "")
    .replace(/_/g, " ");

  return {
    index: isSensex ? "SENSEX" : "NIFTY",
    tf: is5M ? "5M" : "1M",
    mode: isITM ? "ITM" : "ATM",
    dir: isCE ? "CE" : "PE",
    cleanName,
  };
}

function InstrumentPanel({ contract, qty, entryTime, entryPrice, ltp, pnl, stopLoss, takeProfit, exitTime }) {
  const pct = pctReturn(entryPrice, ltp);
  const closed = Boolean(exitTime);
  return (
    <div className="rounded-lg border border-subtle bg-surface2/90 p-3.5 backdrop-blur-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono text-sm font-semibold tracking-wide text-primary">{contract}</div>
          {qty != null && <div className="text-xs text-faint">Qty: {qty}</div>}
          <div className="mt-2 flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5 rounded bg-surface3 px-2 py-1">
              <Badge variant="accent">BUY</Badge>
              <span className="font-mono tabular-nums font-semibold">{fmtRupee(entryPrice)}</span>
            </div>
            <div className="flex items-center gap-1.5 rounded bg-surface3 px-2 py-1">
              <Badge variant={closed ? "bear" : "neutral"}>{closed ? "SELL" : "LTP"}</Badge>
              <span className="font-mono tabular-nums font-semibold">{fmtRupee(ltp)}</span>
            </div>
          </div>
        </div>
        <div className="text-right">
          {pct != null && (
            <div className={`font-mono text-xs font-semibold ${pnlClass(pct)}`}>
              {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
            </div>
          )}
          <div className={`font-mono text-lg font-bold tabular-nums ${pnlClass(pnl)}`}>
            {pnl != null && pnl >= 0 ? "+" : ""}{fmtRupee(pnl)}
          </div>
          <div className="mt-1 text-[11px] text-faint">{closed ? fmtTime(exitTime) : fmtTime(entryTime)}</div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-subtle pt-2 text-xs text-faint">
        <div>SL: <span className="font-mono font-medium text-bear">{fmtRupee(stopLoss)}</span></div>
        <div>TP: <span className="font-mono font-medium text-bull">{fmtRupee(takeProfit)}</span></div>
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

function StrategyCard({ row, pendingSignal, viewMode }) {
  const [expanded, setExpanded] = useState(false);
  const [squaringOff, setSquaringOff] = useState(false);
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

  return (
    <div className={`relative overflow-hidden rounded-xl border border-subtle bg-surface transition-all duration-200 hover:border-border-strong ${entered ? "ring-1 ring-bull/40 bg-surface/95" : ""}`}>
      {/* Top Header Row */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${meta.index === "NIFTY" ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/20" : "bg-purple-500/15 text-purple-400 border border-purple-500/20"}`}>
                {meta.index}
              </span>
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-surface3 text-faint">
                {meta.tf}
              </span>
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${meta.mode === "ITM" ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20" : "bg-blue-500/15 text-blue-400 border border-blue-500/20"}`}>
                {meta.mode}
              </span>
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${meta.dir === "CE" ? "bg-bull/15 text-bull" : "bg-bear/15 text-bear"}`}>
                {meta.dir}
              </span>
            </div>
            <h4 className="mt-1.5 font-semibold text-sm tracking-wide text-primary line-clamp-1" title={row.strategy}>
              {row.strategy}
            </h4>
          </div>

          <div className="text-right">
            <div className="text-[10px] font-medium uppercase tracking-wider text-faint">Today P&amp;L</div>
            <div className={`font-mono text-base font-bold tabular-nums ${pnlClass(row.today_pnl)}`}>
              {row.today_pnl > 0 ? "+" : ""}{fmtRupee(row.today_pnl)}
            </div>
          </div>
        </div>

        {/* Status indicator bar */}
        <div className="mt-3 flex items-center justify-between rounded-lg bg-surface2/70 px-3 py-2 border border-subtle/60">
          <div className="flex items-center gap-2">
            <StatusBeacon entered={entered} />
            <span className={`text-xs font-medium ${entered ? "text-bull font-semibold" : "text-warn"}`}>
              {entered ? "Signal Entered • Live Position" : "Waiting for Entry Signal"}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            {entered && (
              <button
                onClick={handleSquareOff}
                disabled={squaringOff}
                className="rounded border border-bear/40 bg-bear/10 px-2 py-1 text-xs font-medium text-bear transition hover:bg-bear/20 disabled:opacity-50"
              >
                {squaringOff ? "Closing…" : "Square Off"}
              </button>
            )}
            {hasDetails && (
              <button
                onClick={() => setExpanded((e) => !e)}
                className="flex items-center gap-1 rounded bg-surface3 px-2 py-1 text-xs font-medium text-muted transition hover:bg-surface4 hover:text-primary"
              >
                Details
                <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.15 }}>
                  <ChevronDown className="h-3.5 w-3.5" />
                </motion.span>
              </button>
            )}
            <button
              onClick={() => setShowAnalytics(true)}
              className="rounded bg-accent px-2.5 py-1 text-xs font-medium text-white shadow-sm transition hover:bg-accent/90"
            >
              Show Strategy
            </button>
          </div>
        </div>

        {pendingSignal && <PendingSignalBanner signal={pendingSignal} />}

        {/* Expandable Order Details Panel */}
        <AnimatePresence initial={false}>
          {expanded && (row.entry || row.last_closed) && (
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
                    contract={row.last_closed.contract} qty={row.last_closed.qty}
                    entryTime={row.last_closed.entry_time} entryPrice={row.last_closed.entry_price}
                    ltp={row.last_closed.exit_price} pnl={row.last_closed.pnl}
                    stopLoss={row.last_closed.stop_loss} takeProfit={row.last_closed.take_profit}
                    exitTime={row.last_closed.exit_time}
                  />
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
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
      const isSensex = name.startsWith("SENSEX");
      const is5M = name.includes("_5M_");
      const isITM = name.includes("_ITM");
      const isCE = name.includes("_BULLISH") || name.includes("_SUPPORT_BOUNCE");
      const isEntered = s.status === "SIGNAL_ENTERED";

      if (filterTab === "nifty" && isSensex) return false;
      if (filterTab === "sensex" && !isSensex) return false;
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

  const activeCount = strategies.filter((s) => s.status === "SIGNAL_ENTERED").length;
  const niftyCount = strategies.filter((s) => !s.strategy.startsWith("SENSEX")).length;
  const sensexCount = strategies.filter((s) => s.strategy.startsWith("SENSEX")).length;
  const fiveMCount = strategies.filter((s) => s.strategy.includes("_5M_")).length;
  const oneMCount = strategies.filter((s) => !s.strategy.includes("_5M_")).length;

  return (
    <div className="space-y-4">
      {/* Header Controls & Filter Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-subtle bg-surface p-3.5 sm:p-4">
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => setFilterTab("all")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "all" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            All ({strategies.length})
          </button>
          <button
            onClick={() => setFilterTab("nifty")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "nifty" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            NIFTY ({niftyCount})
          </button>
          <button
            onClick={() => setFilterTab("sensex")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "sensex" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            SENSEX ({sensexCount})
          </button>
          <button
            onClick={() => setFilterTab("5m")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "5m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            5M ITM ({fiveMCount})
          </button>
          <button
            onClick={() => setFilterTab("1m")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "1m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            1M ATM ({oneMCount})
          </button>
          <button
            onClick={() => setFilterTab("ce")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "ce" ? "bg-bull text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            Bullish (CE)
          </button>
          <button
            onClick={() => setFilterTab("pe")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${filterTab === "pe" ? "bg-bear text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
          >
            Bearish (PE)
          </button>
          {activeCount > 0 && (
            <button
              onClick={() => setFilterTab("active")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 transition ${filterTab === "active" ? "bg-bull text-white" : "bg-bull/15 text-bull border border-bull/30"}`}
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
              className="w-full rounded-lg border border-subtle bg-surface2 py-1.5 pl-8 pr-3 text-xs text-primary placeholder-faint focus:border-accent focus:outline-none"
            />
          </div>
          <div className="flex items-center rounded-lg border border-subtle bg-surface2 p-0.5">
            <button
              onClick={() => setViewMode("grid")}
              className={`rounded p-1.5 text-xs transition ${viewMode === "grid" ? "bg-surface text-primary shadow-sm" : "text-faint hover:text-primary"}`}
              title="Grid View"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`rounded p-1.5 text-xs transition ${viewMode === "list" ? "bg-surface text-primary shadow-sm" : "text-faint hover:text-primary"}`}
              title="List View"
            >
              <List className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Strategies List / Grid */}
      {filteredStrategies.length === 0 ? (
        <div className="rounded-xl border border-subtle bg-surface py-12 text-center text-faint">
          No strategies match the selected filter.
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredStrategies.map((row) => (
            <StrategyCard
              key={row.strategy}
              row={row}
              pendingSignal={pendingSignals.find((s) => s.strategy === row.strategy)}
              viewMode={viewMode}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredStrategies.map((row) => (
            <StrategyCard
              key={row.strategy}
              row={row}
              pendingSignal={pendingSignals.find((s) => s.strategy === row.strategy)}
              viewMode={viewMode}
            />
          ))}
        </div>
      )}
    </div>
  );
}
