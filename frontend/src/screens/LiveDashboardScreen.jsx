import { useMarketState } from "../hooks/useMarketStream";
import { SignalsTable } from "../components/SignalsTable";
import { PositionsTable } from "../components/PositionsTable";
import { PnlSummaryCard } from "../components/PnlSummaryCard";
import { StrategyStatusList } from "../components/StrategyStatusCard";
import { NiftyHeader } from "../components/NiftyHeader";

export function LiveDashboardScreen() {
  const state = useMarketState();

  return (
    <div className="space-y-4">
      <NiftyHeader state={state} />
      <StrategyStatusList strategies={state.strategy_status} />
      <SignalsTable signals={state.signals} pendingSignals={state.pending_signals} />
      <PositionsTable positions={state.positions} />
      <PnlSummaryCard pnl={state.pnl} />
    </div>
  );
}
