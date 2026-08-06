import { useEffect, useState } from "react";
import { fetchPnlReport, downloadPnlExport } from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { DateRangePicker } from "../components/DateRangePicker";
import { DailyPnlChart } from "../components/DailyPnlChart";
import { StrategyDetailsDrawer } from "../components/StrategyDetailsDrawer";
import { DownloadIcon } from "../components/icons";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
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
            <DownloadIcon className="h-4 w-4" />
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
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
              {[
                { label: "Trades", value: report.combined.trades, plain: true },
                { label: "Gross P&L", value: fmt(report.combined.gross_pnl), cls: pnlClass(report.combined.gross_pnl) },
                { label: "Charges", value: fmt(report.combined.charges) },
                { label: "Net P&L", value: fmt(report.combined.net_pnl), cls: pnlClass(report.combined.net_pnl) },
                { label: "Wallet Balance", value: fmt(report.combined.wallet_balance) },
              ].map((item) => (
                <div key={item.label}>
                  <div className="text-xs text-faint">{item.label}</div>
                  <div className={`text-lg font-semibold tabular-nums ${item.cls ?? ""}`}>{item.value}</div>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Equity Curve">
            <DailyPnlChart daily={report.daily_net_pnl} />
          </Card>
        </>
      )}

      {report && view === "individual" && (
        <Card title="Strategy Performance">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-faint">
                <th className="pb-1 font-normal">Strategy</th>
                <th className="pb-1 font-normal">Trades</th>
                <th className="pb-1 font-normal">Win %</th>
                <th className="pb-1 font-normal">Gross P&amp;L</th>
                <th className="pb-1 font-normal">Charges</th>
                <th className="pb-1 font-normal">Net P&amp;L</th>
                <th className="pb-1 font-normal">Wallet</th>
                <th className="pb-1 font-normal"></th>
              </tr>
            </thead>
            <tbody>
              {report.strategies.map((s) => (
                <tr key={s.strategy} className="border-t border-subtle">
                  <td className="py-1.5 font-medium">{s.strategy}</td>
                  <td className="py-1.5 tabular-nums">{s.trades}</td>
                  <td className="py-1.5 tabular-nums">{s.win_rate}%</td>
                  <td className={`py-1.5 tabular-nums ${pnlClass(s.gross_pnl)}`}>{fmt(s.gross_pnl)}</td>
                  <td className="py-1.5 tabular-nums text-muted">{fmt(s.charges)}</td>
                  <td className={`py-1.5 tabular-nums font-medium ${pnlClass(s.net_pnl)}`}>{fmt(s.net_pnl)}</td>
                  <td className="py-1.5 tabular-nums">{fmt(s.wallet_balance)}</td>
                  <td className="py-1.5 text-right">
                    <button onClick={() => setDetailsFor(s.strategy)} className="text-xs font-medium text-accent hover:underline">
                      Show Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {detailsFor && <StrategyDetailsDrawer strategy={detailsFor} onClose={() => setDetailsFor(null)} />}
    </div>
  );
}
