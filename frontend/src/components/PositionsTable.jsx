import { Card } from "./ui/Card";

export function PositionsTable({ positions }) {
  return (
    <Card title={`Open Positions (${positions.length})`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-faint">
            <th className="pb-1 font-normal">Contract</th>
            <th className="pb-1 font-normal">Entry</th>
            <th className="pb-1 font-normal">SL</th>
            <th className="pb-1 font-normal">TP</th>
            <th className="pb-1 font-normal">Strategy</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 && (
            <tr><td colSpan={5} className="py-3 text-center text-faint">No open positions</td></tr>
          )}
          {positions.map((p) => (
            <tr key={p.order_id} className="border-t border-subtle">
              <td className="py-1.5 font-medium">{p.contract ?? p.symbol}</td>
              <td className="py-1.5">Rs.{p.entry_price?.toFixed(2)}</td>
              <td className="py-1.5 text-bear">Rs.{p.stop_loss?.toFixed(2)}</td>
              <td className="py-1.5 text-bull">Rs.{p.take_profit?.toFixed(2)}</td>
              <td className="py-1.5 text-muted">{p.strategy}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
