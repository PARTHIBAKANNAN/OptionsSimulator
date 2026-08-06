import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";

function Sparkline({ points, positive }) {
  const width = 120;
  const height = 32;
  if (!points || points.length < 2) {
    return <div style={{ width, height }} />;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const scaleX = (i) => (i / (points.length - 1)) * width;
  const scaleY = (v) => height - ((v - min) / range) * height;
  const path = points.map((v, i) => `${scaleX(i)},${scaleY(v)}`).join(" ");

  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline points={path} fill="none" strokeWidth={1.8}
                stroke={positive ? "rgb(var(--bull))" : "rgb(var(--bear))"} />
    </svg>
  );
}

function marketStatePill(mode, exchangeOpen) {
  if (mode !== "live") return { label: "REPLAY", variant: "accent" };
  if (exchangeOpen) return { label: "MARKET OPEN", variant: "bull" };
  return { label: "MARKET CLOSED", variant: "neutral" };
}

export function NiftyHeader({ state }) {
  const { nifty_price, nifty_prev_close, nifty_change, nifty_change_pct, nifty_sparkline,
    mode, exchange_open, fyers_authenticated, timestamp } = state;

  const hasPrice = nifty_price != null;
  const positive = (nifty_change ?? 0) >= 0;
  const pill = marketStatePill(mode, exchange_open);

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xs text-faint">NIFTY 50</div>
            <div className="font-mono text-3xl font-semibold tabular-nums">
              {hasPrice ? nifty_price.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
            </div>
          </div>

          {hasPrice && nifty_change != null && (
            <div className={`font-mono text-sm font-medium tabular-nums ${positive ? "text-bull" : "text-bear"}`}>
              <div>{positive ? "+" : ""}{nifty_change.toLocaleString("en-IN", { maximumFractionDigits: 2 })} pts</div>
              <div>({positive ? "+" : ""}{nifty_change_pct}%)</div>
            </div>
          )}

          <Sparkline points={nifty_sparkline} positive={positive} />
        </div>

        <div className="flex flex-col items-end gap-1.5 text-right">
          <div className="flex items-center gap-2">
            <Badge variant={pill.variant}>{pill.label}</Badge>
            {mode === "live" && (
              <Badge variant={fyers_authenticated ? "bull" : "warn"}>
                {fyers_authenticated ? "Fyers connected" : "Awaiting daily login"}
              </Badge>
            )}
          </div>
          <div className="text-xs text-faint">
            {!exchange_open && nifty_prev_close != null && (
              <span>Prev close {nifty_prev_close.toLocaleString("en-IN", { maximumFractionDigits: 2 })} · </span>
            )}
            {timestamp ? new Date(timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}
          </div>
        </div>
      </div>
    </Card>
  );
}
