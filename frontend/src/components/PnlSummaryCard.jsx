import { useEffect, useState } from "react";
import { Card } from "./ui/Card";
import { fetchPnlReport } from "../hooks/usePaperTradingSync";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
}

function Tile({ label, value, valueClass = "" }) {
  return (
    <div className="rounded-lg border border-subtle bg-surface2 px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className={`font-mono text-lg font-bold tabular-nums ${valueClass}`}>{value}</div>
    </div>
  );
}

// Today's consolidated P&L across every strategy (both indices) -- reuses the same
// /api/paper/pnl/report endpoint the P&L Summary screen uses, just scoped to range=today, so no
// new backend work was needed to move this out of a live-only realized/unrealized split.
export function PnlSummaryCard() {
  const [combined, setCombined] = useState(null);

  useEffect(() => {
    let cancelled = false;
    function load() {
      fetchPnlReport({ range: "today" }).then((r) => {
        if (!cancelled) setCombined(r.combined);
      }).catch(() => {});
    }
    load();
    const interval = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  if (!combined) {
    return <Card title="Today's P&L"><div className="py-2 text-sm text-faint">Loading…</div></Card>;
  }

  return (
    <Card title="Today's P&L">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Trades" value={combined.trades} />
        <Tile label="Gross P&L" value={fmt(combined.gross_pnl)} valueClass={pnlClass(combined.gross_pnl)} />
        <Tile label="Charges" value={fmt(combined.charges)} />
        <Tile label="Net P&L" value={fmt(combined.net_pnl)} valueClass={pnlClass(combined.net_pnl)} />
      </div>
    </Card>
  );
}
