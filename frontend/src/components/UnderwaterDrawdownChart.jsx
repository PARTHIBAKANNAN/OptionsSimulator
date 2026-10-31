import { useMemo, useRef, useState, useEffect } from "react";

function fmtRupee(v) {
  if (v == null || isNaN(v)) return "—";
  return `₹ ${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function UnderwaterDrawdownChart({ dailyBreakdown = {} }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(600);
  const height = 180;
  const padL = 65;
  const padR = 20;
  const padT = 15;
  const padB = 25;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) setWidth(entries[0].contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { points, maxDd, maxDaysUnderwater, currentDd } = useMemo(() => {
    const sortedDates = Object.keys(dailyBreakdown).sort();
    if (sortedDates.length === 0) {
      return { points: [], maxDd: 0, maxDaysUnderwater: 0, currentDd: 0 };
    }

    let cum = 0;
    let peak = 0;
    let mDd = 0;
    let daysUnderwater = 0;
    let maxDays = 0;

    const pts = sortedDates.map((dateStr) => {
      const dayPnl = Number(dailyBreakdown[dateStr] || 0);
      cum += dayPnl;
      if (cum > peak) {
        peak = cum;
        daysUnderwater = 0;
      } else {
        daysUnderwater++;
        if (daysUnderwater > maxDays) maxDays = daysUnderwater;
      }
      const dd = cum - peak; // <= 0
      if (dd < mDd) mDd = dd;

      return {
        date: dateStr,
        drawdown: dd,
      };
    });

    const cDd = pts.length > 0 ? pts[pts.length - 1].drawdown : 0;
    return { points: pts, maxDd: mDd, maxDaysUnderwater: maxDays, currentDd: cDd };
  }, [dailyBreakdown]);

  if (points.length < 2) {
    return (
      <div ref={containerRef} className="flex h-36 items-center justify-center text-xs font-mono text-faint">
        Awaiting multi-day backtest series to construct underwater drawdown envelope.
      </div>
    );
  }

  const minDd = maxDd * 1.15 || -10000;
  const scaleX = (i) => padL + (i / (points.length - 1)) * (width - padL - padR);
  const scaleY = (v) => padT + (v / minDd) * (height - padT - padB);

  const zeroY = scaleY(0);
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)},${scaleY(p.drawdown)}`).join(" ");
  const areaPath = `${linePath} L ${scaleX(points.length - 1)},${zeroY} L ${scaleX(0)},${zeroY} Z`;

  return (
    <div ref={containerRef} className="space-y-2 font-mono">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-3">
          <span>Max Portfolio Drawdown: <strong className="text-rose-400">{fmtRupee(maxDd)}</strong></span>
          <span className="text-slate-600">|</span>
          <span>Longest Waterline: <strong className="text-amber-400">{maxDaysUnderwater} Days</strong></span>
        </div>
        <div className="text-[11px] text-slate-400">
          Current State: <strong className={currentDd === 0 ? "text-emerald-400" : "text-rose-400"}>
            {currentDd === 0 ? "At All-Time Equity High" : `${fmtRupee(currentDd)} below peak`}
          </strong>
        </div>
      </div>

      <div className="relative w-full bg-slate-950/60 rounded-xl border border-slate-800/80 p-2 overflow-hidden">
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
          <defs>
            <linearGradient id="underwaterGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.05" />
            </linearGradient>
          </defs>

          {/* Zero Level Reference Line */}
          <line x1={padL} y1={zeroY} x2={width - padR} y2={zeroY} stroke="#334155" strokeWidth="1.5" strokeDasharray="3 3" />
          <text x={padL - 8} y={zeroY + 4} fill="#64748b" fontSize="10" textAnchor="end">₹0 (Peak)</text>

          {/* Min DD Reference Line */}
          <line x1={padL} y1={scaleY(maxDd)} x2={width - padR} y2={scaleY(maxDd)} stroke="rgba(244, 63, 94, 0.2)" strokeWidth="1" strokeDasharray="2 2" />
          <text x={padL - 8} y={scaleY(maxDd) + 4} fill="#f43f5e" fontSize="10" textAnchor="end">{fmtRupee(maxDd)}</text>

          {/* Area & Stroke */}
          <path d={areaPath} fill="url(#underwaterGrad)" />
          <path d={linePath} fill="none" stroke="#f43f5e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}
