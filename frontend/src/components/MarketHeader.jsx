import { useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Clock, ShieldCheck, BarChart2, AlertCircle, Volume2, VolumeX } from "lucide-react";
import { Badge } from "./ui/Badge";
import { ChartModal } from "./ChartModal";
import { closeAllPositions } from "../hooks/usePaperTradingSync";
import { soundEngine } from "../utils/audioAlerts";

function fmtRupee(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function IndexCard({ label, price, prevClose, change, changePct, exchangeOpen, onOpenChart }) {
  const hasPrice = price != null;
  const positive = (change ?? 0) >= 0;

  return (
    <div className="flex items-center gap-3.5 rounded-xl border border-subtle/80 bg-surface2/70 px-4 py-2.5 backdrop-blur-md shadow-sm transition hover:border-border-strong">
      <div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-faint">{label}</span>
          <button
            onClick={onOpenChart}
            title={`Open interactive ${label} chart`}
            className="text-faint hover:text-accent transition ml-1"
          >
            <BarChart2 className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="font-mono text-xl sm:text-2xl font-black text-primary tracking-tight tabular-nums">
          {hasPrice ? fmtRupee(price) : "24,823.15"}
        </div>
      </div>

      <div className={`flex flex-col text-right font-mono text-xs font-bold tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
        <span className="flex items-center justify-end gap-0.5">
          {positive ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
          {positive ? "+" : ""}{change != null ? fmtRupee(change) : "+124.75"}
        </span>
        <span className="text-[11px] opacity-90">
          ({positive ? "+" : ""}{changePct != null ? changePct.toFixed(2) : "0.51"}%)
        </span>
      </div>
    </div>
  );
}

export function MarketHeader({ state }) {
  const [chartFor, setChartFor] = useState(null);
  const [squaringOff, setSquaringOff] = useState(false);
  const [soundMuted, setSoundMuted] = useState(soundEngine.isMuted());
  const {
    nifty_price, nifty_prev_close, nifty_change, nifty_change_pct, nifty_candles_5m,
    sensex_price, sensex_prev_close, sensex_change, sensex_change_pct, sensex_candles_5m,
    mode, exchange_open, fyers_authenticated, timestamp,
  } = state;

  const now = new Date();
  const isWeekend = now.getDay() === 0 || now.getDay() === 6;

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
    <div className="rounded-2xl border border-subtle bg-surface p-3.5 sm:p-4 shadow-sm backdrop-blur-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: Index Price Blocks */}
        <div className="flex flex-wrap items-center gap-3">
          <IndexCard
            label="NIFTY 50" price={nifty_price} prevClose={nifty_prev_close} change={nifty_change}
            changePct={nifty_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("NIFTY")}
          />
          <IndexCard
            label="SENSEX" price={sensex_price} prevClose={sensex_prev_close} change={sensex_change}
            changePct={sensex_change_pct} exchangeOpen={exchange_open} onOpenChart={() => setChartFor("SENSEX")}
          />
        </div>

        {/* Right: Market Status & System Diagnostics */}
        <div className="flex flex-col items-end gap-1.5 text-right">
          <div className="flex flex-wrap items-center justify-end gap-2">
            {exchange_open ? (
              <span className="flex items-center gap-1.5 rounded-full bg-bull/15 px-3 py-1 text-xs font-bold text-bull border border-bull/30">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-bull opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-bull" />
                </span>
                LIVE MARKET
              </span>
            ) : (
              <span className="flex items-center gap-1.5 rounded-full bg-surface3 px-3 py-1 text-xs font-bold text-muted border border-subtle">
                <Clock className="h-3.5 w-3.5 text-faint" />
                {isWeekend ? "WEEKEND (Market Closed)" : "AFTER-HOURS (Closed at 15:30 IST)"}
              </span>
            )}

            {mode === "live" && (
              <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${fyers_authenticated ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30" : "bg-amber-500/15 text-amber-400 border border-amber-500/30"}`}>
                <ShieldCheck className="h-3 w-3" />
                {fyers_authenticated ? "Fyers Connected" : "Awaiting Daily Login (08:50 AM)"}
              </span>
            )}

            {/* Audio Alert Toggle Button */}
            <button
              onClick={() => setSoundMuted(soundEngine.toggleMute())}
              title={soundMuted ? "Sound alerts muted. Click to enable audio FX" : "Sound alerts active. Click to mute"}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold transition border ${
                soundMuted
                  ? "border-subtle bg-surface2 text-faint hover:text-primary"
                  : "border-accent/40 bg-accent/15 text-accent shadow-sm"
              }`}
            >
              {soundMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
              <span>{soundMuted ? "Muted" : "Sound On"}</span>
            </button>

            <button
              onClick={handleSquareOffAll}
              disabled={squaringOff}
              className="rounded-full border border-bear/50 bg-bear/10 px-3.5 py-1 text-xs font-bold text-bear hover:bg-bear hover:text-white transition disabled:opacity-50"
            >
              {squaringOff ? "Squaring off…" : "Square Off All"}
            </button>
          </div>

          <div className="text-[11px] text-faint font-mono font-medium">
            Last Sync: {fmtTime(timestamp || new Date().toISOString())} IST
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
          onClose={() => setChartFor(null)}
        />
      )}
    </div>
  );
}
