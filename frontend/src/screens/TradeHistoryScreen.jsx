import { usePaperTradingSync, useTradeHistory } from "../hooks/usePaperTradingSync";
import { Card } from "../components/ui/Card";
import { EquityCurveChart } from "../components/EquityCurveChart";

function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function TradeHistoryScreen() {
  usePaperTradingSync();
  const { trades, loading, error } = useTradeHistory();

  return (
    <div className="space-y-4">
      <Card title="Equity Curve">
        <EquityCurveChart trades={trades} />
      </Card>

      <Card title={`Closed Trades (${trades.length})`}>
        {error && <p className="text-bear">{error}</p>}
        {loading && !error && <p className="text-faint">Loading…</p>}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-faint">
              <th className="pb-1 font-normal">Exit Time</th>
              <th className="pb-1 font-normal">Symbol</th>
              <th className="pb-1 font-normal">Entry</th>
              <th className="pb-1 font-normal">Exit</th>
              <th className="pb-1 font-normal">Reason</th>
              <th className="pb-1 font-normal">P&amp;L</th>
              <th className="pb-1 font-normal">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {!loading && trades.length === 0 && (
              <tr><td colSpan={7} className="py-3 text-center text-faint">No closed trades yet</td></tr>
            )}
            {trades.map((t) => (
              <tr key={t.order_id} className="border-t border-subtle">
                <td className="py-1.5">{formatDateTime(t.exit_time)}</td>
                <td className="py-1.5 font-medium">{t.symbol}</td>
                <td className="py-1.5">Rs.{Number(t.entry_price).toFixed(2)}</td>
                <td className="py-1.5">Rs.{Number(t.exit_price).toFixed(2)}</td>
                <td className="py-1.5 text-muted">{t.exit_reason}</td>
                <td className={`py-1.5 ${t.realized_pnl >= 0 ? "text-bull" : "text-bear"}`}>
                  Rs.{Number(t.realized_pnl).toLocaleString("en-IN")}
                </td>
                <td className="py-1.5 text-muted">{t.strategy}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
