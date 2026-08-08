import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { fetchPnlReport, downloadPnlExport } from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { DateRangePicker } from "../components/DateRangePicker";
import { DailyPnlChart } from "../components/DailyPnlChart";
import { StrategyAnalyticsModal } from "../components/StrategyAnalyticsModal";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
}

function StatTile({ label, value, valueClass = "" }) {
  return (
    <div className="rounded-lg border border-subtle bg-surface2 px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className={`font-mono text-lg font-bold tabular-nums ${valueClass}`}>{value}</div>
    </div>
  );
}

export function PnlSummaryScreen() {
  const [view, setView] = useState("individual"); // individual | combined
  const [range, setRange] = useState("today");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [detailsFor, setDetailsFor] = useState(null);
  const [exporting, setExporting] = useState(false);

  const params = { range, ...(range === "custom" ? { start: customStart, end: customEnd } : {}) };
  const canQuery = range !== "custom" || (customStart && customEnd);

  useEffect(() => {
    if (!canQuery) return;
    fetchPnlReport(params).then(setReport).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, customStart, customEnd]);

  async function handleExport() {
    setExporting(true);
    try {
      await downloadPnlExport(params);
    } catch (e) {
      setError(e.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-1 rounded-lg bg-surface3 p-1">
            {["individual", "combined"].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                  view === v ? "bg-accent text-white" : "text-muted hover:text-primary"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
          <button
            onClick={handleExport}
            disabled={exporting || !canQuery}
            className="flex items-center gap-1.5 rounded-lg bg-surface3 px-3 py-1.5 text-sm font-medium text-muted hover:text-primary disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            {exporting ? "Exporting…" : "Export to Excel"}
          </button>
        </div>
        <div className="mt-3">
          <DateRangePicker
            range={range} onChange={setRange} customStart={customStart} customEnd={customEnd}
            onCustomChange={(s, e) => { setCustomStart(s); setCustomEnd(e); }}
          />
        </div>
      </Card>

      {error && <Card><p className="text-bear">{error}</p></Card>}
      {!report && !error && <Card><p className="text-faint">Loading…</p></Card>}

      {report && view === "combined" && (
        <>
          <Card title="Combined Performance">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <StatTile label="Trades" value={report.combined.trades} />
              <StatTile label="Gross P&L" value={fmt(report.combined.gross_pnl)} valueClass={pnlClass(report.combined.gross_pnl)} />
              <StatTile label="Charges" value={fmt(report.combined.charges)} />
              <StatTile label="Net P&L" value={fmt(report.combined.net_pnl)} valueClass={pnlClass(report.combined.net_pnl)} />
              <StatTile label="Wallet Balance" value={fmt(report.combined.wallet_balance)} />
            </div>
          </Card>
          <Card title="Equity Curve">
            <DailyPnlChart daily={report.daily_net_pnl} />
          </Card>
        </>
      )}

      {report && view === "individual" && (
        <Card title="Strategy Performance">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-faint">
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Strategy</th>
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Trades</th>
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Win %</th>
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Gross P&amp;L</th>
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Charges</th>
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Net P&amp;L</th>
                  <th className="pb-2 text-xs font-semibold uppercase tracking-wider">Wallet</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody>
                {report.strategies.map((s) => (
                  <tr key={s.strategy} className="border-t border-subtle hover:bg-surface2">
                    <td className="py-2 font-medium">{s.strategy}</td>
                    <td className="py-2 tabular-nums">{s.trades}</td>
                    <td className="py-2 tabular-nums">{s.win_rate}%</td>
                    <td className={`py-2 font-mono tabular-nums ${pnlClass(s.gross_pnl)}`}>{fmt(s.gross_pnl)}</td>
                    <td className="py-2 font-mono tabular-nums text-muted">{fmt(s.charges)}</td>
                    <td className={`py-2 font-mono tabular-nums font-medium ${pnlClass(s.net_pnl)}`}>{fmt(s.net_pnl)}</td>
                    <td className="py-2 font-mono tabular-nums">{fmt(s.wallet_balance)}</td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => setDetailsFor(s.strategy)}
                        className="rounded bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90"
                      >
                        Show Strategy
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {detailsFor && <StrategyAnalyticsModal strategy={detailsFor} onClose={() => setDetailsFor(null)} />}
    </div>
  );
}
