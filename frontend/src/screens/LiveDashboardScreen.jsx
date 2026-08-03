import { useMarketState } from "../hooks/useMarketStream";
import { SignalsTable } from "../components/SignalsTable";
import { PositionsTable } from "../components/PositionsTable";
import { PnlSummaryCard } from "../components/PnlSummaryCard";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

export function LiveDashboardScreen() {
  const state = useMarketState();

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between">
          <div className="text-2xl font-semibold">
            {state.nifty_price != null ? state.nifty_price.toLocaleString("en-IN", { maximumFractionDigits: 1 }) : "—"}
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={state.mode === "live" ? "accent" : "neutral"}>{state.mode ?? "connecting"}</Badge>
            <Badge variant={state.market_open ? "bull" : "neutral"}>
              {state.market_open ? "RUNNING" : "STOPPED"}
            </Badge>
            {state.mode === "live" && (
              <Badge variant={state.fyers_authenticated ? "bull" : "bear"}>
                {state.fyers_authenticated ? "Fyers connected" : "Fyers not connected"}
              </Badge>
            )}
          </div>
        </div>
      </Card>

      <SignalsTable signals={state.signals} pendingSignals={state.pending_signals} />
      <PositionsTable positions={state.positions} />
      <PnlSummaryCard pnl={state.pnl} />
    </div>
  );
}
