import { useMarketState } from "../hooks/useMarketStream";
import { PnlSummaryCard } from "../components/PnlSummaryCard";
import { StrategyStatusList } from "../components/StrategyStatusCard";
import { MarketHeader } from "../components/MarketHeader";

export function LiveDashboardScreen() {
  const state = useMarketState();

  return (
    <div className="space-y-4">
      <MarketHeader state={state} />
      <PnlSummaryCard />
      <StrategyStatusList strategies={state.strategy_status} pendingSignals={state.pending_signals} />
    </div>
  );
}
