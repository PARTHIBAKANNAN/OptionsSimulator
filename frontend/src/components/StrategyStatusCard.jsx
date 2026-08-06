import { useState } from "react";
import { Card } from "./ui/Card";
import { ChevronDownIcon } from "./icons";
import { StrategyDetailsDrawer } from "./StrategyDetailsDrawer";

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

function StatusDot({ entered }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${entered ? "bg-bull" : "bg-warn"}`} />;
}

function SignalDetailsGrid({ contract, entryTime, entryPrice, ltp, pnl, stopLoss, takeProfit, exitTime }) {
  return (
    <div className="mt-3 grid grid-cols-2 gap-y-2 rounded-lg bg-surface2 p-3 text-sm sm:grid-cols-4">
      <div>
        <div className="text-xs text-faint">Contract</div>
        <div className="font-medium">{contract}</div>
      </div>
      <div>
        <div className="text-xs text-faint">Entry Time</div>
        <div>{fmtTime(entryTime)}</div>
      </div>
      <div>
        <div className="text-xs text-faint">Entry Premium</div>
        <div className="tabular-nums">{fmtRupee(entryPrice)}</div>
      </div>
      <div>
        <div className="text-xs text-faint">{exitTime ? "Exit Price" : "LTP"}</div>
        <div className="tabular-nums">{fmtRupee(ltp)}</div>
      </div>
      <div>
        <div className="text-xs text-faint">Stop Loss</div>
        <div className="tabular-nums text-bear">{fmtRupee(stopLoss)}</div>
      </div>
      <div>
        <div className="text-xs text-faint">Take Profit</div>
        <div className="tabular-nums text-bull">{fmtRupee(takeProfit)}</div>
      </div>
      <div>
        <div className="text-xs text-faint">{exitTime ? "Exit Time" : "P&L"}</div>
        <div className={exitTime ? "" : `tabular-nums font-medium ${pnlClass(pnl)}`}>
          {exitTime ? fmtTime(exitTime) : fmtRupee(pnl)}
        </div>
      </div>
      {exitTime && (
        <div>
          <div className="text-xs text-faint">P&amp;L</div>
          <div className={`tabular-nums font-medium ${pnlClass(pnl)}`}>{fmtRupee(pnl)}</div>
        </div>
      )}
    </div>
  );
}

function StrategyStatusRow({ row, onShowDetails }) {
  const [expanded, setExpanded] = useState(false);
  const entered = row.status === "SIGNAL_ENTERED";
  const hasDetails = Boolean(row.entry || row.last_closed_today);

  return (
    <div className="border-t border-subtle py-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-medium">{row.strategy}</span>
          <span className={`flex items-center gap-1.5 text-sm ${entered ? "text-bull" : "text-warn"}`}>
            <StatusDot entered={entered} />
            {entered ? "Signal Entered" : "Waiting for Entry Signal"}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-sm">
            <span className="text-faint">Today P&amp;L: </span>
            <span className={`font-medium tabular-nums ${pnlClass(row.today_pnl)}`}>{fmtRupee(row.today_pnl)}</span>
          </div>
          {hasDetails && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-muted hover:bg-surface3 hover:text-primary"
            >
              Signal details
              <ChevronDownIcon className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
            </button>
          )}
          <button
            onClick={() => onShowDetails(row.strategy)}
            className="rounded px-2 py-1 text-xs font-medium text-accent hover:bg-accent/10"
          >
            Show Details
          </button>
        </div>
      </div>

      {expanded && row.entry && (
        <SignalDetailsGrid
          contract={row.entry.contract} entryTime={row.entry.entry_time} entryPrice={row.entry.entry_price}
          ltp={row.entry.ltp} pnl={row.entry.trade_pnl} stopLoss={row.entry.stop_loss} takeProfit={row.entry.take_profit}
        />
      )}
      {expanded && !row.entry && row.last_closed_today && (
        <SignalDetailsGrid
          contract={row.last_closed_today.contract} entryTime={row.last_closed_today.entry_time}
          entryPrice={row.last_closed_today.entry_price} ltp={row.last_closed_today.exit_price}
          pnl={row.last_closed_today.pnl} stopLoss={row.last_closed_today.stop_loss}
          takeProfit={row.last_closed_today.take_profit} exitTime={row.last_closed_today.exit_time}
        />
      )}
    </div>
  );
}

export function StrategyStatusList({ strategies }) {
  const [detailsFor, setDetailsFor] = useState(null);

  return (
    <Card title={`Strategies (${strategies.length})`}>
      {strategies.length === 0 && <div className="py-3 text-center text-faint">No strategies loaded</div>}
      {strategies.map((row) => (
        <StrategyStatusRow key={row.strategy} row={row} onShowDetails={setDetailsFor} />
      ))}
      {detailsFor && <StrategyDetailsDrawer strategy={detailsFor} onClose={() => setDetailsFor(null)} />}
    </Card>
  );
}
