import { Badge } from "./ui/Badge";

export function StrategyRankTable({ title, rows, topN = 3 }) {
  const ranked = [...rows].sort((a, b) => (b.profit_factor - a.profit_factor) || (b.win_rate - a.win_rate));
  return (
    <div>
      {title && <div className="mb-2 text-sm font-medium text-muted">{title}</div>}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-faint">
            <th className="pb-1 font-normal">#</th>
            <th className="pb-1 font-normal">Strategy</th>
            <th className="pb-1 font-normal">Trades</th>
            <th className="pb-1 font-normal">Win%</th>
            <th className="pb-1 font-normal">PF</th>
            <th className="pb-1 font-normal">P&amp;L</th>
            <th className="pb-1 font-normal">DD%</th>
            <th className="pb-1 font-normal">Status</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((r, i) => (
            <tr key={r.strategy} className="border-t border-subtle">
              <td className="py-1.5">{i + 1}</td>
              <td className="py-1.5 font-medium">{r.strategy}</td>
              <td className="py-1.5">{r.total_trades}</td>
              <td className="py-1.5">{r.win_rate}%</td>
              <td className="py-1.5">{r.profit_factor}</td>
              <td className={`py-1.5 ${r.total_pnl >= 0 ? "text-bull" : "text-bear"}`}>
                Rs.{r.total_pnl?.toLocaleString("en-IN")}
              </td>
              <td className="py-1.5">{r.max_drawdown_pct}%</td>
              <td className="py-1.5">
                {i < topN && r.total_trades > 0 ? <Badge variant="accent">DEPLOY</Badge> : <span className="text-faint">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
