import { useState } from "react";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { ChartIcon } from "./icons";
import { ChartModal } from "./ChartModal";
import { closeAllPositions } from "../hooks/usePaperTradingSync";

function marketStatePill(mode, exchangeOpen) {
  if (mode !== "live") return { label: "REPLAY", variant: "accent", dot: "bg-accent" };
  if (exchangeOpen) return { label: "MARKET OPEN", variant: "bull", dot: "bg-bull animate-pulse" };
  return { label: "MARKET CLOSED", variant: "neutral", dot: "bg-faint" };
}

function IndexBlock({ label, price, prevClose, change, changePct, exchangeOpen, onOpenChart }) {
  const hasPrice = price != null;
  const positive = (change ?? 0) >= 0;

  return (
    <div className="flex items-center gap-3">
      <div>
        <div className="text-xs text-faint">{label}</div>
        <div className="font-mono text-2xl font-semibold tabular-nums">
          {hasPrice ? price.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
        </div>
      </div>

      {hasPrice && change != null && (
        <div className={`font-mono text-xs font-medium tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
          <div>{positive ? "+" : ""}{change.toLocaleString("en-IN", { maximumFractionDigits: 2 })} pts</div>
          <div>({positive ? "+" : ""}{changePct}%)</div>
        </div>
      )}

      {!exchangeOpen && prevClose != null && (
        <div className="text-xs text-faint">Prev {prevClose.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
      )}

      <button
        onClick={onOpenChart}
        title={`${label} chart`}
        className="rounded p-1.5 text-faint hover:bg-surface3 hover:text-accent"
      >
        <ChartIcon className="h-4 w-4" />
      </button>
    </div>
  );
}

export function MarketHeader({ state }) {
  const [chartFor, setChartFor] = useState(null); // 'NIFTY' | 'SENSEX' | null
  const [squaringOff, setSquaringOff] = useState(false);
  const {
    nifty_price, nifty_prev_close, nifty_change, nifty_change_pct, nifty_candles_5m,
    sensex_price, sensex_prev_close, sensex_change, sensex_change_pct, sensex_candles_5m,
    mode, exchange_open, fyers_authenticated, timestamp,
  } = state;

  const pill = marketStatePill(mode, exchange_open);

  async function handleSquareOffAll() {
    if (!window.confirm("Square off ALL open positions across every strategy? This cannot be undone.")) return;
    setSquaringOff(true);
    try {
      await closeAllPositions();
    } catch (e) {
      window.alert(e.message || "Square off failed");
    } finally {
      setSquaringOff(false);
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-6">
          <IndexBlock
            label="NIFTY 50" price={nifty_price} prevClose={nifty_prev_close} change={nifty_change}
            changePct={nifty_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("NIFTY")}
          />
          <IndexBlock
            label="SENSEX" price={sensex_price} prevClose={sensex_prev_close} change={sensex_change}
            changePct={sensex_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("SENSEX")}
          />
        </div>

        <div className="flex flex-col items-end gap-1.5 text-right">
          <div className="flex flex-wrap items-center justify-end gap-1.5 sm:gap-2">
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${pill.dot}`} />
            <Badge variant={pill.variant}>{pill.label}</Badge>
            {mode === "live" && (
              <Badge variant={fyers_authenticated ? "bull" : "warn"}>
                {fyers_authenticated ? "Fyers connected" : "Awaiting daily login"}
              </Badge>
            )}
            <button
              onClick={handleSquareOffAll}
              disabled={squaringOff}
              className="rounded border border-bear/40 px-2 py-0.5 text-xs font-medium text-bear hover:bg-bear/10 disabled:opacity-50"
            >
              {squaringOff ? "Squaring off…" : "Square Off All"}
            </button>
          </div>
          <div className="text-xs text-faint">
            {timestamp ? new Date(timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}
          </div>
        </div>
      </div>

      {chartFor && (
        <ChartModal
          label={chartFor === "NIFTY" ? "NIFTY 50" : "SENSEX"}
          candles={chartFor === "NIFTY" ? nifty_candles_5m : sensex_candles_5m}
          price={chartFor === "NIFTY" ? nifty_price : sensex_price}
          change={chartFor === "NIFTY" ? nifty_change : sensex_change}
          changePct={chartFor === "NIFTY" ? nifty_change_pct : sensex_change_pct}
          onClose={() => setChartFor(null)}
        />
      )}
    </Card>
  );
}
