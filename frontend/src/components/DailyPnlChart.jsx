// Cumulative net-P&L curve from a {date, net_pnl}[] daily series — same hand-rolled SVG approach
// as EquityCurveChart.jsx, just fed a pre-aggregated daily series instead of a raw trade list.
import { useEffect, useRef, useState } from "react";

const HEIGHT = 200;
const PADDING = 10;

export function DailyPnlChart({ daily }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(600);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  let cumulative = 0;
  const points = (daily || []).map((d) => (cumulative += d.net_pnl));

  if (points.length < 2) {
    return (
      <div ref={containerRef} className="flex h-48 items-center justify-center text-sm text-faint">
        Not enough closed trades in this range for a graph
      </div>
    );
  }

  const min = Math.min(0, ...points);
  const max = Math.max(0, ...points);
  const range = max - min || 1;
  const scaleX = (i) => PADDING + (i / (points.length - 1)) * (width - 2 * PADDING);
  const scaleY = (v) => HEIGHT - PADDING - ((v - min) / range) * (HEIGHT - 2 * PADDING);
  const path = points.map((v, i) => `${scaleX(i)},${scaleY(v)}`).join(" ");
  const zeroY = scaleY(0);
  const final = points[points.length - 1];

  return (
    <div ref={containerRef}>
      <svg width={width} height={HEIGHT}>
        <line x1={0} y1={zeroY} x2={width} y2={zeroY} stroke="rgb(var(--border-subtle))" strokeDasharray="4 4" />
        <polyline points={path} fill="none" stroke={final >= 0 ? "rgb(var(--bull))" : "rgb(var(--bear))"} strokeWidth={2} />
      </svg>
    </div>
  );
}
