import { useEffect, useState } from "react";
import {
  fetchBacktestReport, fetchBacktestDailyBreakdown, fetchBacktestCapitalRequirements,
} from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { StrategyRankTable } from "../components/StrategyRankTable";

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
  const ce = strategies.filter((s) => s.direction === "CE");
  const pe = strategies.filter((s) => s.direction === "PE");

  return (
    <div className="space-y-4">
      <Card title="Bullish (CE) Strategies">
        <StrategyRankTable
          title="" rows={ce} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements}
        />
      </Card>
      <Card title="Bearish (PE) Strategies">
        <StrategyRankTable
          title="" rows={pe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements}
        />
      </Card>
    </div>
  );
}
