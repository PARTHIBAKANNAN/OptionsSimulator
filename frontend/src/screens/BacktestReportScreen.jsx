import { useEffect, useMemo, useState } from "react";
import {
  fetchBacktestReport, fetchBacktestDailyBreakdown, fetchBacktestCapitalRequirements,
} from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { StrategyRankTable } from "../components/StrategyRankTable";
import { StrategyPnlComparisonChart } from "../components/StrategyPnlComparisonChart";
import { TrendingUp, ShieldCheck, Zap, Layers, Trophy } from "lucide-react";

function fmtRupee(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pnlClass(v) {
  if (v == null) return "";
  return v > 0 ? "text-bull" : v < 0 ? "text-bear" : "";
}

function InsightTile({ label, value, sublabel, valueClass = "", icon: Icon }) {
  return (
    <div className="rounded-xl border border-subtle bg-surface p-4 backdrop-blur-sm shadow-sm transition hover:border-border-strong">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">{label}</div>
        {Icon && <Icon className="h-4 w-4 text-accent opacity-80" />}
      </div>
      <div className={`mt-2 font-mono text-xl sm:text-2xl font-bold tabular-nums ${valueClass}`}>{value}</div>
      {sublabel && <div className="mt-1 text-xs text-faint">{sublabel}</div>}
    </div>
  );
}

export function BacktestReportScreen() {
  const [report, setReport] = useState(null);
  const [dailyBreakdown, setDailyBreakdown] = useState({});
  const [capitalRequirements, setCapitalRequirements] = useState({});
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("all");

  useEffect(() => {
    fetchBacktestReport().then(setReport).catch((e) => setError(e.message));
    fetchBacktestDailyBreakdown().then(setDailyBreakdown).catch(() => {});
    fetchBacktestCapitalRequirements().then(setCapitalRequirements).catch(() => {});
  }, []);

  if (error) {
    return <Card><p className="text-faint">{error}</p></Card>;
  }
  if (!report) {
    return <Card><p className="text-faint">Loading Backtest Report…</p></Card>;
  }

  const strategies = Object.entries(report)
    .filter(([key]) => key !== "_selected")
    .map(([, value]) => value);

  const isSensex = (s) => s.strategy.startsWith("SENSEX_");
  const isBankNifty = (s) => s.strategy.startsWith("BANKNIFTY_");
  const isNifty = (s) => !isSensex(s) && !isBankNifty(s);
  const is5M = (s) => s.strategy.includes("_5M_");

  const niftyCe = strategies.filter((s) => isNifty(s) && s.direction === "CE");
  const niftyPe = strategies.filter((s) => isNifty(s) && s.direction === "PE");
  const sensexCe = strategies.filter((s) => isSensex(s) && s.direction === "CE");
  const sensexPe = strategies.filter((s) => isSensex(s) && s.direction === "PE");
  const bankniftyCe = strategies.filter((s) => isBankNifty(s) && s.direction === "CE");
  const bankniftyPe = strategies.filter((s) => isBankNifty(s) && s.direction === "PE");

  const totalPnl = strategies.reduce((sum, s) => sum + s.total_pnl, 0);
  const totalTrades = strategies.reduce((sum, s) => sum + s.total_trades, 0);
  const withTrades = strategies.filter((s) => s.total_trades > 0);
  const avgWinRate = withTrades.length
    ? withTrades.reduce((sum, s) => sum + s.win_rate, 0) / withTrades.length : 0;
  const best = withTrades.length ? withTrades.reduce((a, b) => (b.total_pnl > a.total_pnl ? b : a)) : null;

  return (
    <div className="space-y-6">
      {/* Top 4 KPI Tiles */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <InsightTile
          label="Combined 1-Yr Net P&L"
          value={fmtRupee(Math.round(totalPnl))}
          valueClass="text-bull font-black"
          sublabel={`${strategies.length} Master Strategies Combined`}
          icon={TrendingUp}
        />
        <InsightTile
          label="Overall Win Rate"
          value={`${avgWinRate.toFixed(1)}%`}
          valueClass="text-bull"
          sublabel={`Across ${totalTrades.toLocaleString()} Total Signals`}
          icon={ShieldCheck}
        />
        <InsightTile
          label="Total Trades Executed"
          value={totalTrades.toLocaleString()}
          valueClass="text-primary"
          sublabel="Zero Freeze & Duplication Free"
          icon={Zap}
        />
        <InsightTile
          label="Top Strategy Performer"
          value={best ? fmtRupee(best.total_pnl) : "—"}
          valueClass="text-bull"
          sublabel={best ? best.strategy : ""}
          icon={Trophy}
        />
      </div>

      {/* Strategy Comparison Chart */}
      <div className="rounded-xl border border-subtle bg-surface p-4 sm:p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-sm text-primary tracking-wide">P&amp;L Comparison &middot; All {strategies.length} Strategies</h3>
            <p className="text-xs text-faint mt-0.5">Historical 1-year performance breakdown sorted by profitability</p>
          </div>
        </div>
        <StrategyPnlComparisonChart strategies={strategies} />
      </div>

      {/* Tabs Filter Bar for Leaderboards */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-subtle bg-surface p-3">
        <button
          onClick={() => setActiveTab("all")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${activeTab === "all" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
        >
          All Strategies ({strategies.length})
        </button>
        <button
          onClick={() => setActiveTab("nifty")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${activeTab === "nifty" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
        >
          NIFTY Suite (10)
        </button>
        <button
          onClick={() => setActiveTab("sensex")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${activeTab === "sensex" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
        >
          SENSEX Suite (11)
        </button>
        <button
          onClick={() => setActiveTab("banknifty")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${activeTab === "banknifty" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
        >
          BANKNIFTY Suite (11)
        </button>
        <button
          onClick={() => setActiveTab("5m")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${activeTab === "5m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
        >
          5M ITM Suite ({strategies.filter(is5M).length})
        </button>
        <button
          onClick={() => setActiveTab("1m")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${activeTab === "1m" ? "bg-accent text-white shadow-sm" : "bg-surface2 text-muted hover:bg-surface3 hover:text-primary"}`}
        >
          1M ATM Baseline ({strategies.filter((s) => !is5M(s)).length})
        </button>
      </div>

      {/* Tabbed Leaderboard Tables */}
      <div className="space-y-6">
        {(activeTab === "all" || activeTab === "nifty") && (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
                <span className="h-2 w-2 rounded-full bg-cyan-400" /> NIFTY Bullish (CE) Strategies
              </div>
              <StrategyRankTable rows={niftyCe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
                <span className="h-2 w-2 rounded-full bg-cyan-400" /> NIFTY Bearish (PE) Strategies
              </div>
              <StrategyRankTable rows={niftyPe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
            </div>
          </>
        )}

        {(activeTab === "all" || activeTab === "sensex") && (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
                <span className="h-2 w-2 rounded-full bg-purple-400" /> SENSEX Bullish (CE) Strategies
              </div>
              <StrategyRankTable rows={sensexCe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
                <span className="h-2 w-2 rounded-full bg-purple-400" /> SENSEX Bearish (PE) Strategies
              </div>
              <StrategyRankTable rows={sensexPe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
            </div>
          </>
        )}

        {(activeTab === "all" || activeTab === "banknifty") && (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
                <span className="h-2 w-2 rounded-full bg-emerald-400" /> BANKNIFTY Bullish (CE) Strategies
              </div>
              <StrategyRankTable rows={bankniftyCe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
                <span className="h-2 w-2 rounded-full bg-emerald-400" /> BANKNIFTY Bearish (PE) Strategies
              </div>
              <StrategyRankTable rows={bankniftyPe} dailyBreakdown={dailyBreakdown} capitalRequirements={capitalRequirements} />
            </div>
          </>
        )}

        {activeTab === "5m" && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
              <span className="h-2 w-2 rounded-full bg-amber-400" /> 12 High-Conviction 5-Minute ITM Strategies
            </div>
            <StrategyRankTable
              rows={strategies.filter((s) => is5M(s))}
              dailyBreakdown={dailyBreakdown}
              capitalRequirements={capitalRequirements}
            />
          </div>
        )}

        {activeTab === "1m" && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-semibold text-xs text-primary uppercase tracking-wider">
              <span className="h-2 w-2 rounded-full bg-blue-400" /> 9 Standard 1-Minute ATM Baseline Strategies
            </div>
            <StrategyRankTable
              rows={strategies.filter((s) => !is5M(s))}
              dailyBreakdown={dailyBreakdown}
              capitalRequirements={capitalRequirements}
            />
          </div>
        )}
      </div>
    </div>
  );
}
