import { useMarketState } from "../hooks/useMarketStream";
import { SignalsTable } from "../components/SignalsTable";
import { PositionsTable } from "../components/PositionsTable";
import { PnlSummaryCard } from "../components/PnlSummaryCard";
import { StrategyStatusList } from "../components/StrategyStatusCard";
import { MarketHeader } from "../components/MarketHeader";

export function LiveDashboardScreen() {
  const state = useMarketState();

  return (
    <div className="space-y-4">
      <MarketHeader state={state} />
      <StrategyStatusList strategies={state.strategy_status} />
      <SignalsTable signals={state.signals} pendingSignals={state.pending_signals} />
      <PositionsTable positions={state.positions} />
      <PnlSummaryCard pnl={state.pnl} />
    </div>
  );
}
