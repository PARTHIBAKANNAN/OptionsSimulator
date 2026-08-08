import { useEffect, useState } from "react";
import {
  fetchBacktestReport, fetchBacktestDailyBreakdown, fetchBacktestCapitalRequirements,
} from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { StrategyRankTable } from "../components/StrategyRankTable";
import { StrategyPnlComparisonChart } from "../components/StrategyPnlComparisonChart";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
}

function InsightTile({ label, value, valueClass = "" }) {
  return (
    <div className="rounded-lg border border-subtle bg-surface2 px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className={`font-mono text-lg font-bold tabular-nums ${valueClass}`}>{value}</div>
    </div>
  );
}

export function BacktestReportScreen() {
  const [report, setReport] = useState(null);
  const [dailyBreakdown, setDailyBreakdown] = useState({});
  const [capitalRequirements, setCapitalRequirements] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchBacktestReport().then(setReport).catch((e) => setError(e.message));
    fetchBacktestDailyBreakdown().then(setDailyBreakdown).catch(() => {});
    fetchBacktestCapitalRequirements().then(setCapitalRequirements).catch(() => {});
  }, []);

  if (error) {
    return <Card><p className="text-faint">{error}</p></Card>;
  }
  if (!report) {
    return <Card><p className="text-faint">Loading…</p></Card>;
  }

  const strategies = Object.entries(report)
    .filter(([key]) => key !== "_selected")
    .map(([, value]) => value);

  const isSensex = (s) => s.strategy.startsWith("SENSEX_");
  const niftyCe = strategies.filter((s) => !isSensex(s) && s.direction === "CE");
  const niftyPe = strategies.filter((s) => !isSensex(s) && s.direction === "PE");
  const sensexCe = strategies.filter((s) => isSensex(s) && s.direction === "CE");
  const sensexPe = strategies.filter((s) => isSensex(s) && s.direction === "PE");
  const hedge = strategies.filter((s) => s.direction === "HEDGE");

  const totalPnl = strategies.reduce((sum, s) => sum + s.total_pnl, 0);
  const withTrades = strategies.filter((s) => s.total_trades > 0);
  const avgWinRate = withTrades.length
    ? withTrades.reduce((sum, s) => sum + s.win_rate, 0) / withTrades.length : 0;
  const best = withTrades.length ? withTrades.reduce((a, b) => (b.total_pnl > a.total_pnl ? b : a)) : null;
  const worst = withTrades.length ? withTrades.reduce((a, b) => (b.total_pnl < a.total_pnl ? b : a)) : null;

  const allDates = Object.values(dailyBreakdown).flatMap((days) => days.map((d) => d.date)).sort();
  const dateRange = allDates.length ? `${allDates[0]} to ${allDates[allDates.length - 1]}` : "—";

  return (
    <div className="space-y-4">
      <Card title="Backtest Overview">
        <div className="mb-3 text-xs text-faint">Data range: {dateRange}</div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <InsightTile label="Strategies Backtested" value={strategies.length} />
          <InsightTile label="Combined P&L" value={fmtRupee(Math.round(totalPnl))} valueClass={pnlClass(totalPnl)} />
          <InsightTile label="Avg Win Rate" value={`${avgWinRate.toFixed(1)}%`} />
          <InsightTile
            label="Best Performer"
            value={best ? fmtRupee(best.total_pnl) : "—"}
            valueClass="text-bull"
          />
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-faint">
          {best && <div>Best: <span className="text-primary">{best.strategy.replace(/^SENSEX_/, "")}</span></div>}
          {worst && (
            <div>Worst: <span className="text-primary">{worst.strategy.replace(/^SENSEX_/, "")}</span> <span className="text-bear">({fmtRupee(worst.total_pnl)})</span></div>
          )}
        </div>
      </Card>

      <Card title="P&L Comparison — All Strategies">
        <StrategyPnlComparisonChart strategies={strategies} />
      </Card>

      <Card title="NIFTY — Bullish (CE) Strategies">
        <StrategyRankTable rows={niftyCe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
      </Card>
      <Card title="NIFTY — Bearish (PE) Strategies">
        <StrategyRankTable rows={niftyPe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
      </Card>
      <Card title="SENSEX — Bullish (CE) Strategies">
        <StrategyRankTable rows={sensexCe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
      </Card>
      <Card title="SENSEX — Bearish (PE) Strategies">
        <StrategyRankTable rows={sensexPe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
      </Card>
      {hedge.length > 0 && (
        <Card title="Expiry-Day Hedge Strategies">
          <StrategyRankTable rows={hedge} topN={hedge.length} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
        </Card>
      )}
    </div>
  );
}
