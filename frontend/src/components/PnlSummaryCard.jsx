import { Card } from "./ui/Card";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function PnlSummaryCard({ pnl }) {
  const items = [
    { label: "Realized", value: pnl.realized_pnl },
    { label: "Unrealized", value: pnl.unrealized_pnl },
    { label: "Total", value: pnl.total_pnl },
    { label: "Today", value: pnl.realized_pnl_today },
  ];
  return (
    <Card title="P&L Summary">
      <div className="grid grid-cols-4 gap-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="text-xs text-faint">{item.label}</div>
            <div className={`text-lg font-semibold ${item.value > 0 ? "text-bull" : item.value < 0 ? "text-bear" : ""}`}>
              {fmt(item.value)}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
