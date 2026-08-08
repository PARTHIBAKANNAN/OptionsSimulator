import { CandleChart } from "./CandleChart";
import { XIcon } from "./icons";

// Centered overlay, same fixed/backdrop pattern as StrategyDetailsDrawer.jsx (which slides in
// from the side instead) -- a chart wants width, not a narrow side panel.
export function ChartModal({ label, candles, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-3xl rounded-lg border border-subtle bg-surface p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted">{label} · 5m</h2>
          <button onClick={onClose} className="rounded p-1 text-faint hover:bg-surface3 hover:text-primary">
            <XIcon className="h-4 w-4" />
          </button>
        </div>
        {candles && candles.length > 0 ? (
          <CandleChart candles={candles} height={420} />
        ) : (
          <div className="flex h-[420px] items-center justify-center text-faint">No candle data yet</div>
        )}
      </div>
    </div>
  );
}
