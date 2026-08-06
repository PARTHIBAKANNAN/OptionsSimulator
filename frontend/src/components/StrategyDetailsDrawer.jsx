import { useEffect, useState } from "react";
import { fetchStrategyOrders } from "../hooks/usePaperTradingSync";

function fmt(v) {
  if (v == null) return "—";
  return `Rs.${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function StrategyDetailsDrawer({ strategy, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    fetchStrategyOrders(strategy).then(setData).catch((e) => setError(e.message));
  }, [strategy]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto bg-surface p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{strategy}</h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-faint hover:bg-surface3 hover:text-primary">
            Close
          </button>
        </div>

        {error && <p className="text-bear">{error}</p>}
        {!data && !error && <p className="text-faint">Loading…</p>}

        {data && (
          <div className="space-y-5">
            {data.wallet && (
              <div className="rounded-lg border border-subtle p-3">
                <div className="mb-1 text-xs font-medium text-faint">WALLET</div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-faint">Balance</div>
                    <div className="text-lg font-semibold tabular-nums">{fmt(data.wallet.balance)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-faint">Allocated</div>
                    <div className="tabular-nums">{fmt(data.wallet.allocated_capital)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-faint">P&amp;L in wallet</div>
                    <div className={`tabular-nums font-medium ${data.wallet.pnl_in_wallet >= 0 ? "text-bull" : "text-bear"}`}>
                      {data.wallet.pnl_in_wallet >= 0 ? "+" : ""}{fmt(data.wallet.pnl_in_wallet)}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {data.current_signal?.status === "SIGNAL_ENTERED" && (
              <div className="rounded-lg border border-bull/30 bg-bull/5 p-3">
                <div className="mb-1 text-xs font-medium text-faint">CURRENTLY OPEN</div>
                <div className="text-sm">
                  {data.current_signal.entry.contract} @ {fmt(data.current_signal.entry.entry_price)}
                  {" — "}LTP {fmt(data.current_signal.entry.ltp)}
                </div>
              </div>
            )}

            <div>
              <div className="mb-2 text-xs font-medium text-faint">
                CLOSED TRADES ({data.closed_trades.length})
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-faint">
                    <th className="pb-1 font-normal">Contract</th>
                    <th className="pb-1 font-normal">Entry</th>
                    <th className="pb-1 font-normal">Exit</th>
                    <th className="pb-1 font-normal">Reason</th>
                    <th className="pb-1 font-normal">Net P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {data.closed_trades.length === 0 && (
                    <tr><td colSpan={5} className="py-3 text-center text-faint">No closed trades yet</td></tr>
                  )}
                  {data.closed_trades.map((t) => (
                    <tr key={t.order_id} className="border-t border-subtle align-top">
                      <td className="py-1.5">
                        <div>{t.contract}</div>
                        <div className="text-xs text-faint">{fmtDateTime(t.entry_time)}</div>
                      </td>
                      <td className="py-1.5 tabular-nums">{fmt(t.entry_price)}</td>
                      <td className="py-1.5 tabular-nums">
                        <div>{fmt(t.exit_price)}</div>
                        <div className="text-xs text-faint">{fmtDateTime(t.exit_time)}</div>
                      </td>
                      <td className="py-1.5 text-muted">{t.exit_reason}</td>
                      <td className={`py-1.5 tabular-nums font-medium ${t.net_pnl >= 0 ? "text-bull" : "text-bear"}`}>
                        {fmt(t.net_pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
