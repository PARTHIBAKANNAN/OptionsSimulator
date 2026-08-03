// Hand-rolled SVG line chart — no charting library dependency, same approach TradeDashBoard uses
// for its own equity curve.
import { useEffect, useRef, useState } from "react";

const HEIGHT = 160;
const PADDING = 8;

export function EquityCurveChart({ trades }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(600);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const ordered = [...trades].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time));
  let cumulative = 0;
  const points = ordered.map((t) => (cumulative += Number(t.realized_pnl) || 0));

  if (points.length < 2) {
    return (
      <div ref={containerRef} className="flex h-40 items-center justify-center text-sm text-faint">
        Not enough closed trades yet for an equity curve
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
