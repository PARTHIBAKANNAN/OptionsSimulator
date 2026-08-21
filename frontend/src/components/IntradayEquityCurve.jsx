import { useMemo } from "react";
import { TrendingUp } from "lucide-react";

function fmtRupee(v) {
  if (v == null) return "—";
  return `₹ ${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

export function IntradayEquityCurve({ todayPnl = 0, closedTrades = [] }) {
  const points = useMemo(() => {
    if (!closedTrades || closedTrades.length === 0) {
      return [
        { time: "09:15", pnl: 0 },
        { time: "Now", pnl: todayPnl },
      ];
    }
    let cum = 0;
    const pts = [{ time: "09:15", pnl: 0 }];
    for (const t of closedTrades) {
      cum += Number(t.realized_pnl ?? t.net_pnl ?? 0);
      const timeStr = t.exit_time ? new Date(t.exit_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "";
      pts.push({ time: timeStr, pnl: cum });
    }
    return pts;
  }, [closedTrades, todayPnl]);

  const pnlVals = points.map((p) => p.pnl);
  const minPnl = Math.min(0, ...pnlVals);
  const maxPnl = Math.max(100, ...pnlVals);
  const range = maxPnl - minPnl || 100;

  const w = 500;
  const h = 100;
  const pad = 12;

  const pathD = points
    .map((p, i) => {
      const x = pad + (i / (points.length - 1 || 1)) * (w - 2 * pad);
      const y = h - pad - ((p.pnl - minPnl) / range) * (h - 2 * pad);
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const isGreen = todayPnl >= 0;
  const strokeColor = isGreen ? "#22c55e" : "#ef4444";
  const fillGrad = isGreen ? "url(#gradGreen)" : "url(#gradRed)";

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-4 shadow-sm backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-bull/15 text-bull border border-bull/20">
            <TrendingUp className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-primary">Live Intraday Equity Curve</h4>
            <p className="text-[11px] text-faint">Real-time cumulative P&amp;L progression across today&apos;s session</p>
          </div>
        </div>
        <div className="text-right">
          <span className={`font-mono text-sm font-extrabold ${isGreen ? "text-bull" : "text-bear"}`}>
            {todayPnl > 0 ? "+" : ""}{fmtRupee(todayPnl)}
          </span>
        </div>
      </div>

      <div className="mt-3 relative h-24 w-full">
        <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-full w-full overflow-visible">
          <defs>
            <linearGradient id="gradGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#22c55e" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="gradRed" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Zero baseline */}
          <line
            x1={pad}
            y1={h - pad - ((0 - minPnl) / range) * (h - 2 * pad)}
            x2={w - pad}
            y2={h - pad - ((0 - minPnl) / range) * (h - 2 * pad)}
            stroke="currentColor"
            strokeDasharray="3 3"
            className="text-subtle/80"
          />

          {/* Fill Area */}
          <path
            d={`${pathD} L ${w - pad},${h - pad} L ${pad},${h - pad} Z`}
            fill={fillGrad}
          />

          {/* Curve stroke */}
          <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}
