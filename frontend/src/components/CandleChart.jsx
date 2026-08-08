import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  createSeriesMarkers,
} from "lightweight-charts";

// `bucket` is minutes-since-midnight IST (see DataManager.get_candles_5m_with_delta).
// lightweight-charts renders UTCTimestamp labels in UTC, not the browser's local timezone, so
// building the epoch from the browser's local wall-clock only round-trips correctly when the
// browser's own zone happens to be UTC. Building it from UTC components instead makes the
// library's UTC-labeled display show the correct IST time regardless of the viewer's timezone --
// same fix TradeDashBoard's CandleChart.jsx uses for this exact issue.
function bucketToTime(bucket) {
  const now = new Date();
  const utcMidnight = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  return Math.floor(utcMidnight / 1000) + bucket * 60;
}

function formatDelta(value) {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${Math.round(abs)}`;
}

const MIN_PX_PER_BAR_FOR_LABELS = 32;

// 5-min candlestick + cumulative tick-rule delta histogram, backed by lightweight-charts --
// mirrors TradeDashBoard's CandleChart.jsx (proven pattern), fed by our own live paper-trading
// data (nifty_candles_5m / sensex_candles_5m) instead of TradeDashBoard's DB-backed candles.
export function CandleChart({ candles, height = 360 }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const deltaSeriesRef = useRef(null);
  const deltaMarkersRef = useRef(null);
  const deltaDataRef = useRef([]);
  const labelsVisibleRef = useRef(false);
  const candlesInitializedRef = useRef(false);
  const prevCandleCountRef = useRef(0);
  const deltaInitializedRef = useRef(false);
  const prevDeltaCountRef = useRef(0);
  const [latestDelta, setLatestDelta] = useState(0);
  const [hoveredDelta, setHoveredDelta] = useState(null);

  function applyDeltaMarkers() {
    const markers = deltaMarkersRef.current;
    if (!markers) return;
    if (!labelsVisibleRef.current || !deltaDataRef.current.length) {
      markers.setMarkers([]);
      return;
    }
    markers.setMarkers(
      deltaDataRef.current.map((d) => ({
        time: d.time,
        position: d.value >= 0 ? "aboveBar" : "belowBar",
        color: d.color,
        shape: "circle",
        size: 0,
        text: formatDelta(d.value),
      })),
    );
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: "rgb(var(--muted))" },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "rgba(255,255,255,0.06)" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "rgb(var(--bull))", downColor: "rgb(var(--bear))",
      borderUpColor: "rgb(var(--bull))", borderDownColor: "rgb(var(--bear))",
      wickUpColor: "rgb(var(--bull))", wickDownColor: "rgb(var(--bear))",
    });

    const deltaSeries = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      1,
    );
    const panes = chart.panes();
    if (panes[0]) panes[0].setStretchFactor(3);
    if (panes[1]) panes[1].setStretchFactor(1);

    const deltaMarkers = createSeriesMarkers(deltaSeries, []);

    const onCrosshairMove = (param) => {
      if (!param.time) {
        setHoveredDelta(null);
        return;
      }
      const point = param.seriesData.get(deltaSeries);
      setHoveredDelta(typeof point?.value === "number" ? point.value : null);
    };
    chart.subscribeCrosshairMove(onCrosshairMove);

    const handleVisibleRangeChange = () => {
      const ts = chartRef.current?.timeScale();
      if (!ts) return;
      const range = ts.getVisibleLogicalRange();
      if (!range) return;
      const barSpan = range.to - range.from;
      const pxWidth = ts.width();
      const perBarPx = barSpan > 0 ? pxWidth / barSpan : 0;
      const shouldShow = perBarPx >= MIN_PX_PER_BAR_FOR_LABELS;
      if (shouldShow === labelsVisibleRef.current) return;
      labelsVisibleRef.current = shouldShow;
      applyDeltaMarkers();
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);

    chartRef.current = chart;
    seriesRef.current = series;
    deltaSeriesRef.current = deltaSeries;
    deltaMarkersRef.current = deltaMarkers;

    return () => {
      chart.unsubscribeCrosshairMove(onCrosshairMove);
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      deltaSeriesRef.current = null;
      deltaMarkersRef.current = null;
    };
  }, []);

  // Candle data -- setData()+fitContent() only on first load; a live update that's just "the
  // last bar changed" or "exactly one new bar appended" uses series.update() instead, which
  // lightweight-charts handles without resetting the user's pan/zoom.
  useEffect(() => {
    if (!seriesRef.current) return;
    const data = (candles || [])
      .map((c) => ({ time: bucketToTime(c.bucket), open: c.open, high: c.high, low: c.low, close: c.close }))
      .sort((a, b) => a.time - b.time);
    if (data.length === 0) return;

    const prevLen = prevCandleCountRef.current;
    if (!candlesInitializedRef.current) {
      seriesRef.current.setData(data);
      chartRef.current?.timeScale().fitContent();
      candlesInitializedRef.current = true;
    } else if (data.length === prevLen || data.length === prevLen + 1) {
      seriesRef.current.update(data[data.length - 1]);
    } else {
      seriesRef.current.setData(data);
    }
    prevCandleCountRef.current = data.length;
  }, [candles]);

  // Cumulative tick-rule delta -- one histogram bar per candle, colored by the sign of the
  // running total (not the per-bar delta), so a string of small down-ticks that hasn't yet
  // erased the day's net buying still reads green.
  useEffect(() => {
    if (!deltaSeriesRef.current) return;
    let cumulative = 0;
    const data = (candles || [])
      .map((c) => {
        cumulative += c.delta || 0;
        return {
          time: bucketToTime(c.bucket), value: cumulative,
          color: cumulative >= 0 ? "rgb(var(--bull))" : "rgb(var(--bear))",
        };
      })
      .sort((a, b) => a.time - b.time);
    setLatestDelta(cumulative);
    deltaDataRef.current = data;
    if (data.length === 0) return;

    const prevLen = prevDeltaCountRef.current;
    if (!deltaInitializedRef.current) {
      deltaSeriesRef.current.setData(data);
      deltaInitializedRef.current = true;
    } else if (data.length === prevLen || data.length === prevLen + 1) {
      deltaSeriesRef.current.update(data[data.length - 1]);
    } else {
      deltaSeriesRef.current.setData(data);
    }
    prevDeltaCountRef.current = data.length;
    applyDeltaMarkers();
  }, [candles]);

  const displayDelta = hoveredDelta ?? latestDelta;
  const isHovering = hoveredDelta != null;

  return (
    <div className="relative w-full" style={{ height }}>
      <div
        className={`absolute top-1.5 right-2.5 z-10 pointer-events-none rounded-md border px-2 py-0.5 text-[10px] font-mono font-bold ${
          isHovering ? "border-accent/50 bg-surface3/95 text-accent" : "border-subtle bg-surface3/80 text-muted"
        }`}
      >
        CVD {formatDelta(displayDelta)}
      </div>
      <div ref={containerRef} style={{ height: "100%" }} className="w-full" />
    </div>
  );
}
