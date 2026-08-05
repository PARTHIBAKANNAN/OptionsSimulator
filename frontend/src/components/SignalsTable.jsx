import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { approveSignal, rejectSignal } from "../hooks/usePaperTradingSync";

function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function SignalsTable({ signals, pendingSignals }) {
  return (
    <Card title="Signals">
      {pendingSignals.length > 0 && (
        <div className="mb-3 space-y-2">
          {pendingSignals.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded border border-accent/40 bg-accent/10 px-3 py-2">
              <div className="text-sm">
                <span className="font-medium">{s.strategy}</span>{" "}
                <Badge variant={s.direction === "CE" ? "bull" : "bear"}>{s.contract ?? s.strike}</Badge>{" "}
                <span className="text-muted">@ Rs.{s.entry_price?.toFixed(2)}</span>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded bg-bull px-3 py-1 text-xs font-medium text-white"
                  onClick={() => approveSignal(s.id)}
                >
                  Approve
                </button>
                <button
                  className="rounded bg-bear px-3 py-1 text-xs font-medium text-white"
                  onClick={() => rejectSignal(s.id)}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-faint">
            <th className="pb-1 font-normal">Time</th>
            <th className="pb-1 font-normal">Strategy</th>
            <th className="pb-1 font-normal">Contract</th>
            <th className="pb-1 font-normal">Entry</th>
            <th className="pb-1 font-normal">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {signals.length === 0 && (
            <tr><td colSpan={5} className="py-3 text-center text-faint">No signals yet</td></tr>
          )}
          {signals.slice(-5).reverse().map((s, i) => (
            <tr key={i} className="border-t border-subtle">
              <td className="py-1.5">{formatTime(s.timestamp)}</td>
              <td className="py-1.5">{s.strategy}</td>
              <td className="py-1.5"><Badge variant={s.direction === "CE" ? "bull" : "bear"}>{s.strike}</Badge></td>
              <td className="py-1.5">Rs.{s.entry_price?.toFixed(2)}</td>
              <td className="py-1.5">{Math.round(s.confidence * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
