import { memo, useState } from "react";
import { TrendingUp, TrendingDown, Clock, BarChart2 } from "lucide-react";
import { ChartModal } from "./ChartModal";
import { ConnectAliceBlueModal } from "./ConnectAliceBlueModal";
import { useSpotPrices } from "../hooks/useMarketStream";

function fmtRupee(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const IndexCard = memo(function IndexCard({ label, price, prevClose, change, changePct, exchangeOpen, onOpenChart }) {
  const hasPrice = price != null;
  const positive = (change ?? 0) >= 0;

  return (
    <div 
      className="group relative flex flex-col justify-between rounded-2xl border border-subtle/80 bg-surface2/60 p-3 sm:p-3.5 backdrop-blur-md shadow-sm transition-all duration-200 hover:border-accent/40 hover:bg-surface2/80 min-w-0"
    >
      {/* Top Header: Index Title & Anchored Fixed Chart Action Button */}
      <div className="flex items-center justify-between gap-2 pb-2 border-b border-subtle/40">
        <span className="text-[11px] font-black uppercase tracking-wider text-muted group-hover:text-primary transition-colors">
          {label === "NIFTY" ? "NIFTY 50" : label}
        </span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpenChart();
          }}
          title={`Open interactive ${label} candlestick chart`}
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold text-faint hover:text-accent bg-surface/90 hover:bg-accent/15 border border-subtle hover:border-accent/30 transition-all cursor-pointer active:scale-95 shrink-0"
        >
          <BarChart2 className="h-3 w-3 text-accent shrink-0" />
          <span>Chart</span>
        </button>
      </div>

      {/* Main Body: Price & Change with Stable Tabular Mono Numbers */}
      <div className="flex items-baseline justify-between gap-2 pt-2.5 min-w-0">
        <div className="font-mono text-base sm:text-xl lg:text-2xl font-black text-primary tracking-tight tabular-nums truncate">
          {hasPrice ? fmtRupee(price) : "—"}
        </div>

        <div className={`flex flex-col items-end shrink-0 font-mono text-[11px] sm:text-xs font-bold tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
          <span className="flex items-center gap-0.5">
            {positive ? <TrendingUp className="h-3 w-3 shrink-0" /> : <TrendingDown className="h-3 w-3 shrink-0" />}
            {positive ? "+" : ""}{change != null ? fmtRupee(change) : "0.00"}
          </span>
          <span className="text-[10px] opacity-85">
            ({positive ? "+" : ""}{changePct != null ? Number(changePct).toFixed(2) : "0.00"}%)
          </span>
        </div>
      </div>
    </div>
  );
});

export function MarketHeader({ state: propState }) {
  const liveSpot = useSpotPrices();
  const state = propState ? { ...propState, ...liveSpot } : liveSpot;
  const [chartFor, setChartFor] = useState(null);
  const [showAliceModal, setShowAliceModal] = useState(false);
  const {
    nifty_price, nifty_prev_close, nifty_change, nifty_change_pct, nifty_candles_5m,
    sensex_price, sensex_prev_close, sensex_change, sensex_change_pct, sensex_candles_5m,
    banknifty_price, banknifty_prev_close, banknifty_change, banknifty_change_pct, banknifty_candles_5m,
    mode, exchange_open, fyers_authenticated, aliceblue_authenticated, broker_authenticated,
    is_connected, corridor_subscribed, timestamp,
    ws_latency_ms, active_quotes_count,
  } = state;
  const isStreaming = Boolean(is_connected);

  const now = new Date();
  const isWeekend = now.getDay() === 0 || now.getDay() === 6;

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-3 sm:p-4 shadow-sm backdrop-blur-sm">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 sm:gap-4">
        {/* Left: 3 Fixed-Grid Index Tickers (equal-width columns, zero width jitter) */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3.5 w-full lg:flex-1">
          <IndexCard
            label="NIFTY" price={nifty_price} prevClose={nifty_prev_close} change={nifty_change}
            changePct={nifty_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("NIFTY")}
          />
          <IndexCard
            label="SENSEX" price={sensex_price} prevClose={sensex_prev_close} change={sensex_change}
            changePct={sensex_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("SENSEX")}
          />
          <IndexCard
            label="BANKNIFTY" price={banknifty_price} prevClose={banknifty_prev_close} change={banknifty_change}
            changePct={banknifty_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("BANKNIFTY")}
          />
        </div>

        {/* Right: Clean, Unified Market Status & Connection Details */}
        <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between lg:justify-center gap-2 pt-2 border-t border-subtle/50 lg:border-t-0 lg:pt-0 shrink-0">
          {/* Single Consolidated Status Pill */}
          <button
            type="button"
            onClick={() => setShowAliceModal(true)}
            title="Click to view broker gateway connection & details"
            className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-bold transition-all border shadow-sm cursor-pointer hover:opacity-90 active:scale-95 bg-surface2/80 border-subtle"
          >
            <span className="relative flex h-2 w-2">
              {exchange_open ? (
                <>
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bull opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-bull" />
                </>
              ) : (
                <span className="relative inline-flex h-2 w-2 rounded-full bg-muted" />
              )}
            </span>

            <span className="text-primary font-bold">
              {exchange_open ? "LIVE" : isWeekend ? "WEEKEND" : "MARKET CLOSED"}
            </span>

            {isStreaming && ws_latency_ms != null && (
              <span className="text-[11px] font-mono font-semibold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                {ws_latency_ms}ms
              </span>
            )}
          </button>

          {/* Compact Subtitle Telemetry */}
          <div className="flex items-center gap-2 text-[11px] font-mono text-faint">
            {active_quotes_count > 0 && (
              <span className="hidden sm:inline">
                {active_quotes_count} quotes
              </span>
            )}
            {active_quotes_count > 0 && <span className="hidden sm:inline opacity-40">•</span>}
            <span>Sync: {fmtTime(timestamp || new Date().toISOString())}</span>
          </div>
        </div>
      </div>


      {chartFor && (
        <ChartModal
          initialIndex={chartFor}
          niftyCandles={nifty_candles_5m}
          niftyPrice={nifty_price}
          niftyChange={nifty_change}
          niftyChangePct={nifty_change_pct}
          sensexCandles={sensex_candles_5m}
          sensexPrice={sensex_price}
          sensexChange={sensex_change}
          sensexChangePct={sensex_change_pct}
          bankniftyCandles={banknifty_candles_5m}
          bankniftyPrice={banknifty_price}
          bankniftyChange={banknifty_change}
          bankniftyChangePct={banknifty_change_pct}
          onClose={() => setChartFor(null)}
        />
      )}

      <ConnectAliceBlueModal
        isOpen={showAliceModal}
        onClose={() => setShowAliceModal(false)}
      />
    </div>
  );
}
