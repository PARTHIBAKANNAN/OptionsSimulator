import { useEffect, useMemo, useState } from "react";
import { Download, Search, TrendingUp, Wallet, ShieldCheck, Zap, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { fetchPnlReport, downloadPnlExport } from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { DateRangePicker } from "../components/DateRangePicker";
import { DailyPnlChart } from "../components/DailyPnlChart";
import { PostMarketJournalCard } from "../components/PostMarketJournalCard";
import { StrategyAnalyticsModal } from "../components/StrategyAnalyticsModal";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "text-muted";
}

function StatTile({ label, value, valueClass = "", icon: Icon }) {
  return (
    <div className="rounded-xl border border-subtle bg-surface2/80 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">{label}</div>
        {Icon && <Icon className="h-4 w-4 text-accent opacity-80" />}
      </div>
      <div className={`mt-2 font-mono text-xl sm:text-2xl font-bold tabular-nums ${valueClass}`}>{value}</div>
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
  const [searchTerm, setSearchTerm] = useState("");
  const [filterTab, setFilterTab] = useState("all");

  // Default sorting: Net P&L High to Low
  const [sortField, setSortField] = useState("net_pnl");
  const [sortOrder, setSortOrder] = useState("desc");

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

  function handleSort(field) {
    if (sortField === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder(field === "strategy" ? "asc" : "desc");
    }
  }

  function SortHeader({ label, field, align = "left" }) {
    const isActive = sortField === field;
    return (
      <th
        onClick={() => handleSort(field)}
        className={`py-2.5 px-3 font-semibold uppercase cursor-pointer select-none transition hover:text-primary ${
          align === "right" ? "text-right" : "text-left"
        } ${isActive ? "text-accent font-bold" : "text-faint"}`}
      >
        <div className={`flex items-center gap-1 ${align === "right" ? "justify-end" : "justify-start"}`}>
          <span>{label}</span>
          {isActive ? (
            sortOrder === "asc" ? (
              <ArrowUp className="h-3 w-3 text-accent" />
            ) : (
              <ArrowDown className="h-3 w-3 text-accent" />
            )
          ) : (
            <ArrowUpDown className="h-3 w-3 opacity-40 hover:opacity-100" />
          )}
        </div>
      </th>
    );
  }

  const allStrategies = report?.strategies ?? [];
  const filteredStrategies = useMemo(() => {
    return allStrategies.filter((s) => {
      const name = s.strategy;
      const isSensex = name.startsWith("SENSEX");
      const is5M = name.includes("_5M_");
      const hasTrades = (s.trades || 0) > 0;
      const isProfit = (s.net_pnl || 0) > 0;

      if (filterTab === "nifty" && isSensex) return false;
      if (filterTab === "sensex" && !isSensex) return false;
      if (filterTab === "5m" && !is5M) return false;
      if (filterTab === "1m" && is5M) return false;
      if (filterTab === "trades" && !hasTrades) return false;
      if (filterTab === "profit" && !isProfit) return false;

      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        return name.toLowerCase().includes(query);
      }
      return true;
    });
  }, [allStrategies, filterTab, searchTerm]);

  const sortedStrategies = useMemo(() => {
    return [...filteredStrategies].sort((a, b) => {
      let valA = a[sortField];
      let valB = b[sortField];

      if (typeof valA === "string") {
        return sortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }

      valA = valA ?? 0;
      valB = valB ?? 0;

      // Push strategies with 0 trades / 0 P&L to the end of the list so active profits and losses stay grouped at the top
      const isZeroA = valA === 0 && (a.trades || 0) === 0;
      const isZeroB = valB === 0 && (b.trades || 0) === 0;

      if (isZeroA && !isZeroB) return 1;  // Move zero-trade strategy to bottom
      if (!isZeroA && isZeroB) return -1; // Keep active strategy at top

      return sortOrder === "asc" ? valA - valB : valB - valA;
    });
  }, [filteredStrategies, sortField, sortOrder]);

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="rounded-xl border border-subtle bg-surface p-4 sm:p-5 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-primary">Live P&amp;L Performance</h2>
              <p className="text-xs text-faint">Realized P&amp;L, broker charges, and per-strategy wallet audits</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center rounded-lg bg-surface2 p-1 border border-subtle text-xs font-medium">
              <button
                onClick={() => setView("individual")}
                className={`rounded-md px-3 py-1 transition ${view === "individual" ? "bg-accent text-white font-semibold shadow-sm" : "text-muted hover:text-primary"}`}
              >
                Individual View
              </button>
              <button
                onClick={() => setView("combined")}
                className={`rounded-md px-3 py-1 transition ${view === "combined" ? "bg-accent text-white font-semibold shadow-sm" : "text-muted hover:text-primary"}`}
              >
                Combined View
              </button>
            </div>

            <button
              onClick={handleExport}
              disabled={exporting || !canQuery}
              className="flex items-center gap-1.5 rounded-lg border border-subtle bg-surface2 px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-surface3 disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              <span>{exporting ? "Exporting…" : "Export to Excel"}</span>
            </button>
          </div>
        </div>

        <div>
          <DateRangePicker
            range={range} onChange={setRange} customStart={customStart} customEnd={customEnd}
            onCustomChange={(s, e) => { setCustomStart(s); setCustomEnd(e); }}
          />
        </div>
      </div>

      {/* 15:35 IST Post-Market AI Trade Journal & Performance Review */}
      <PostMarketJournalCard />

      {error && <Card><p className="text-bear">{error}</p></Card>}
      {!report && !error && <Card><p className="text-faint">Loading P&amp;L Report…</p></Card>}

      {report && view === "combined" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Total Trades" value={report.combined.trades} icon={Zap} />
            <StatTile label="Gross P&L" value={fmt(report.combined.gross_pnl)} valueClass={pnlClass(report.combined.gross_pnl)} icon={TrendingUp} />
            <StatTile label="Net P&L" value={fmt(report.combined.net_pnl)} valueClass={pnlClass(report.combined.net_pnl)} icon={TrendingUp} />
            <StatTile label="Combined Wallet" value={fmt(report.combined.wallet_balance)} valueClass="text-accent" icon={Wallet} />
          </div>

          <div className="rounded-xl border border-subtle bg-surface p-4 sm:p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-faint mb-3">Live Equity Curve</h3>
            <DailyPnlChart daily={report.daily_net_pnl} />
          </div>
        </div>
      )}

      {report && view === "individual" && (
        <div className="rounded-xl border border-subtle bg-surface p-4 sm:p-5 space-y-4">
          {/* Filter Bar & Search */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                onClick={() => setFilterTab("all")}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${filterTab === "all" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
              >
                All ({allStrategies.length})
              </button>
              <button
                onClick={() => setFilterTab("nifty")}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${filterTab === "nifty" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
              >
                NIFTY ({allStrategies.filter((s) => !s.strategy.startsWith("SENSEX")).length})
              </button>
              <button
                onClick={() => setFilterTab("sensex")}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${filterTab === "sensex" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
              >
                SENSEX ({allStrategies.filter((s) => s.strategy.startsWith("SENSEX")).length})
              </button>
              <button
                onClick={() => setFilterTab("5m")}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${filterTab === "5m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
              >
                5M ITM
              </button>
              <button
                onClick={() => setFilterTab("1m")}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${filterTab === "1m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
              >
                1M ATM
              </button>
              <button
                onClick={() => setFilterTab("trades")}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition ${filterTab === "trades" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
              >
                With Trades
              </button>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-faint" />
              <input
                type="text"
                placeholder="Search strategies…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-lg border border-subtle bg-surface2 py-1.5 pl-8 pr-3 text-xs text-primary placeholder-faint focus:border-accent focus:outline-none"
              />
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-subtle">
            <table className="w-full text-xs">
              <thead className="bg-surface2 text-faint">
                <tr>
                  <SortHeader label="Strategy" field="strategy" align="left" />
                  <th className="py-2.5 px-3 text-left font-semibold uppercase">TF</th>
                  <SortHeader label="Trades" field="trades" align="left" />
                  <SortHeader label="Win %" field="win_rate" align="left" />
                  <SortHeader label="Gross P&L" field="gross_pnl" align="right" />
                  <SortHeader label="Charges" field="charges" align="right" />
                  <SortHeader label="Net P&L" field="net_pnl" align="right" />
                  <SortHeader label="Wallet Balance" field="wallet_balance" align="right" />
                  <th className="py-2.5 px-3 text-right font-semibold uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-subtle font-mono">
                {sortedStrategies.map((s) => {
                  const is5M = s.strategy.includes("_5M_");
                  const isSensex = s.strategy.startsWith("SENSEX");

                  return (
                    <tr key={s.strategy} className="hover:bg-surface2/50 transition">
                      <td className="py-2.5 px-3 font-sans font-medium text-primary">
                        <div className="flex items-center gap-1.5">
                          <span className={`h-1.5 w-1.5 rounded-full ${isSensex ? "bg-purple-400" : "bg-cyan-400"}`} />
                          <span>{s.strategy}</span>
                        </div>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${is5M ? "bg-amber-500/15 text-amber-400" : "bg-surface3 text-faint"}`}>
                          {is5M ? "5M" : "1M"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 tabular-nums">{s.trades}</td>
                      <td className="py-2.5 px-3 tabular-nums text-bull font-bold">{s.win_rate}%</td>
                      <td className={`py-2.5 px-3 text-right tabular-nums ${pnlClass(s.gross_pnl)}`}>{fmt(s.gross_pnl)}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-faint">{fmt(s.charges)}</td>
                      <td className={`py-2.5 px-3 text-right font-bold tabular-nums ${pnlClass(s.net_pnl)}`}>{fmt(s.net_pnl)}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-primary font-semibold">{fmt(s.wallet_balance)}</td>
                      <td className="py-2.5 px-3 text-right font-sans">
                        <button
                          onClick={() => setDetailsFor(s.strategy)}
                          className="rounded bg-accent px-2.5 py-1 text-[11px] font-medium text-white transition hover:bg-accent/90 shadow-sm"
                        >
                          Show Strategy
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Individual Trades Log Table */}
          <div className="rounded-xl border border-subtle bg-surface p-4 sm:p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-primary">Executed Individual Trades Log</h3>
                <p className="text-xs text-faint">Detailed record of every trade executed within selected date range</p>
              </div>
              <span className="rounded-full bg-accent/15 px-2.5 py-1 text-xs font-mono font-bold text-accent">
                {(report?.trades || []).length} Executed Trades
              </span>
            </div>

            <div className="overflow-x-auto rounded-xl border border-subtle">
              <table className="w-full text-xs">
                <thead className="bg-surface2 text-faint">
                  <tr>
                    <th className="py-2.5 px-3 text-left font-semibold uppercase">Order ID</th>
                    <th className="py-2.5 px-3 text-left font-semibold uppercase">Strategy</th>
                    <th className="py-2.5 px-3 text-left font-semibold uppercase">Contract Symbol</th>
                    <th className="py-2.5 px-3 text-left font-semibold uppercase">Entry Time</th>
                    <th className="py-2.5 px-3 text-right font-semibold uppercase">Entry Price</th>
                    <th className="py-2.5 px-3 text-left font-semibold uppercase">Exit Time</th>
                    <th className="py-2.5 px-3 text-right font-semibold uppercase">Exit Price</th>
                    <th className="py-2.5 px-3 text-center font-semibold uppercase">Exit Reason</th>
                    <th className="py-2.5 px-3 text-right font-semibold uppercase">Net P&amp;L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-subtle font-mono">
                  {(report?.trades || []).length === 0 ? (
                    <tr>
                      <td colSpan="9" className="py-6 text-center text-xs text-faint font-sans">
                        No individual trades executed for the selected date range.
                      </td>
                    </tr>
                  ) : (
                    (report?.trades || []).map((t) => {
                      const pnl = (t.realized_pnl || 0) - (t.entry_charges || 0) - (t.exit_charges || 0);
                      return (
                        <tr key={t.order_id} className="hover:bg-surface2/50 transition">
                          <td className="py-2.5 px-3 text-muted">{t.order_id}</td>
                          <td className="py-2.5 px-3 font-sans font-medium text-primary">{t.strategy}</td>
                          <td className="py-2.5 px-3 font-bold text-accent">{t.symbol}</td>
                          <td className="py-2.5 px-3 text-faint">{t.entry_time ? new Date(t.entry_time).toLocaleString("en-IN") : "—"}</td>
                          <td className="py-2.5 px-3 text-right text-primary font-medium">{t.entry_price ? fmt(t.entry_price) : "—"}</td>
                          <td className="py-2.5 px-3 text-faint">{t.exit_time ? new Date(t.exit_time).toLocaleString("en-IN") : "—"}</td>
                          <td className="py-2.5 px-3 text-right text-primary font-medium">{t.exit_price ? fmt(t.exit_price) : "—"}</td>
                          <td className="py-2.5 px-3 text-center font-sans">
                            <span className="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase bg-surface3 text-muted border border-subtle">
                              {t.exit_reason || "TSL"}
                            </span>
                          </td>
                          <td className={`py-2.5 px-3 text-right font-bold tabular-nums ${pnlClass(pnl)}`}>
                            {pnl > 0 ? "+" : ""}{fmt(pnl)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {detailsFor && (
        <StrategyAnalyticsModal strategy={detailsFor} mode="live" onClose={() => setDetailsFor(null)} />
      )}
    </div>
  );
}
