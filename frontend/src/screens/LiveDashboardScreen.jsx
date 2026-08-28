import { useMarketState } from "../hooks/useMarketStream";
import { PnlSummaryCard } from "../components/PnlSummaryCard";
import { StrategyStatusList } from "../components/StrategyStatusCard";
import { MarketHeader } from "../components/MarketHeader";
import { ExposureMeter } from "../components/ExposureMeter";
import { IntradayEquityCurve } from "../components/IntradayEquityCurve";
import { PreMarketIntelligenceCard } from "../components/PreMarketIntelligenceCard";
import { PostMarketJournalCard } from "../components/PostMarketJournalCard";
import { IndexHeatmapMatrix } from "../components/IndexHeatmapMatrix";

export function LiveDashboardScreen() {
  const state = useMarketState();

  const totalTodayPnl = state.strategy_status?.reduce((acc, s) => acc + (s.today_pnl || 0), 0) || 0;
  const activePositions = state.positions || [];

  return (
    <div className="space-y-4">
      <MarketHeader state={state} />
      
      {/* Real-time Index Trend Bias Heatmap */}
      <IndexHeatmapMatrix state={state} />

      {/* 08:50 AM Pre-Market Catalyst & Sentiment Card */}
      <PreMarketIntelligenceCard />

      {/* Live Telemetry Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <IntradayEquityCurve todayPnl={totalTodayPnl} />
        <ExposureMeter positions={activePositions} />
      </div>

      <PnlSummaryCard />
      <StrategyStatusList strategies={state.strategy_status} pendingSignals={state.pending_signals} />
    </div>
  );
}
