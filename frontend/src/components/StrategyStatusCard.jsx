import { Card } from "./ui/Card";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
}

function StatusDot({ entered }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${entered ? "bg-bull" : "bg-amber-400"}`}
    />
  );
}

function StrategyStatusRow({ row }) {
  const entered = row.status === "SIGNAL_ENTERED";
  return (
    <div className="border-t border-subtle py-3 first:border-t-0 first:pt-0">
      <div className="flex items-center justify-between">
        <div className="font-medium">{row.strategy}</div>
        <div className="flex items-center gap-1.5 text-sm">
          <StatusDot entered={entered} />
          <span className={entered ? "text-bull" : "text-amber-400"}>
            {entered ? "Signal Entered" : "Waiting for Entry Signal"}
          </span>
        </div>
      </div>

      {entered && row.entry && (
        <div className="mt-2 grid grid-cols-2 gap-y-1 text-sm text-muted sm:grid-cols-4">
          <div>
            <span className="text-faint">Contract: </span>
            {row.entry.contract}
          </div>
          <div>
            <span className="text-faint">Entry: </span>
            {fmtRupee(row.entry.entry_price)}
          </div>
          <div>
            <span className="text-faint">LTP: </span>
            {fmtRupee(row.entry.ltp)}
          </div>
          <div>
            <span className="text-faint">Trade P&amp;L: </span>
            <span className={pnlClass(row.entry.trade_pnl)}>{fmtRupee(row.entry.trade_pnl)}</span>
          </div>
        </div>
      )}

      <div className="mt-1.5 text-sm">
        <span className="text-faint">Today P&amp;L: </span>
        <span className={`font-medium ${pnlClass(row.today_pnl)}`}>{fmtRupee(row.today_pnl)}</span>
      </div>
    </div>
  );
}

export function StrategyStatusList({ strategies }) {
  return (
    <Card title={`Strategies (${strategies.length})`}>
      {strategies.length === 0 && <div className="py-3 text-center text-faint">No strategies loaded</div>}
      {strategies.map((row) => (
        <StrategyStatusRow key={row.strategy} row={row} />
      ))}
    </Card>
  );
}
