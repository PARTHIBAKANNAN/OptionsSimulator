import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import { useTheme } from "../contexts/ThemeContext";

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

function computeEmaSeries(data, span) {
  if (!data || data.length === 0) return [];
  const k = 2 / (span + 1);
  const result = [];
  let ema = data[0].close;
  for (let i = 0; i < data.length; i++) {
    const price = data[i].close;
    ema = i === 0 ? price : price * k + ema * (1 - k);
    result.push({ time: data[i].time, value: Number(ema.toFixed(2)) });
  }
  return result;
}

const MIN_PX_PER_BAR_FOR_LABELS = 32;

function readCandleColors() {
  const styles = getComputedStyle(document.documentElement);
  const getRgb = (prop, fallback) => {
    const raw = (styles.getPropertyValue(prop) || "").trim();
    if (!raw) return fallback;
    if (raw.startsWith("#")) return raw;
    const numbers = raw.match(/\d+/g);
    if (numbers && numbers.length >= 3) {
      return `rgb(${numbers[0]}, ${numbers[1]}, ${numbers[2]})`;
    }
    return fallback;
  };

  const up = getRgb("--bull", "rgb(34, 197, 94)");
  const down = getRgb("--bear", "rgb(239, 68, 68)");
  return { up, down };
}

export function CandleChart({ candles = [], tradeMarkers = [], height = 400 }) {
  const { theme } = useTheme() || {};
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const ema20SeriesRef = useRef(null);
  const ema50SeriesRef = useRef(null);
  const candleMarkersRef = useRef(null);
  const deltaSeriesRef = useRef(null);
  const deltaMarkersRef = useRef(null);
  const deltaDataRef = useRef([]);
  const labelsVisibleRef = useRef(false);
  const candlesInitializedRef = useRef(false);
  const prevCandleCountRef = useRef(0);
  const [showEma, setShowEma] = useState(true);
  const [hoveredDelta, setHoveredDelta] = useState(null);
  const [latestDelta, setLatestDelta] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const { up, down } = readCandleColors();
    const isDark = theme === "dark";

    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: isDark ? "rgb(158, 165, 176)" : "rgb(86, 91, 100)" },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 8,
        minBarSpacing: 3,
        fixLeftEdge: true,
        rightOffset: 12,
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: up, downColor: down,
      borderUpColor: up, borderDownColor: down,
      wickUpColor: up, wickDownColor: down,
    });

    const ema20Series = chart.addSeries(LineSeries, {
      color: "#06b6d4",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA 20",
    });

    const ema50Series = chart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA 50",
    });

    const deltaSeries = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      1,
    );

    const panes = chart.panes();
    if (panes[0]) panes[0].setStretchFactor(3);
    if (panes[1]) panes[1].setStretchFactor(1);

    const candleMarkers = createSeriesMarkers(series, []);
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

    chartRef.current = chart;
    seriesRef.current = series;
    ema20SeriesRef.current = ema20Series;
    ema50SeriesRef.current = ema50Series;
    candleMarkersRef.current = candleMarkers;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      ema20SeriesRef.current = null;
      ema50SeriesRef.current = null;
      candleMarkersRef.current = null;
    };
  }, []);

  // Update Candles and EMAs
  useEffect(() => {
    if (!seriesRef.current) return;
    const data = (candles || [])
      .map((c) => ({
        time: bucketToTime(c.bucket),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      .sort((a, b) => a.time - b.time);

    if (data.length === 0) return;

    seriesRef.current.setData(data);

    if (ema20SeriesRef.current && showEma) {
      ema20SeriesRef.current.setData(computeEmaSeries(data, 20));
    }
    if (ema50SeriesRef.current && showEma) {
      ema50SeriesRef.current.setData(computeEmaSeries(data, 50));
    }

    if (!candlesInitializedRef.current) {
      chartRef.current?.timeScale().scrollToPosition(0, false);
      candlesInitializedRef.current = true;
    }
  }, [candles, showEma]);

  return (
    <div className="relative w-full rounded-2xl overflow-hidden border border-subtle bg-surface" style={{ height }}>
      {/* Top Chart Controls */}
      <div className="absolute top-2 left-3 z-10 flex items-center gap-2">
        <button
          onClick={() => setShowEma((v) => !v)}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold border transition ${
            showEma
              ? "bg-accent/15 text-accent border-accent/30"
              : "bg-surface2 text-faint border-subtle hover:text-primary"
          }`}
        >
          EMA (20, 50)
        </button>
        {showEma && (
          <div className="flex items-center gap-2 text-[10px] font-mono font-semibold">
            <span className="text-cyan-400">● EMA20</span>
            <span className="text-orange-400">● EMA50</span>
          </div>
        )}
      </div>

      <div ref={containerRef} style={{ height: "100%" }} className="w-full" />
    </div>
  );
}
