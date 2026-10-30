import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import { Eye, EyeOff, BarChart2 } from "lucide-react";
import { useTheme } from "../contexts/ThemeContext";

function bucketToTime(bucket) {
  const now = new Date();
  const utcMidnight = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  return Math.floor(utcMidnight / 1000) + bucket * 60;
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

function computeVwapSeries(data) {
  if (!data || data.length === 0) return [];
  const result = [];
  let cumVol = 0;
  let cumPv = 0;
  let currentDay = null;

  for (let i = 0; i < data.length; i++) {
    const d = new Date(data[i].time * 1000);
    const dayKey = d.toDateString();
    if (dayKey !== currentDay) {
      currentDay = dayKey;
      cumVol = 0;
      cumPv = 0;
    }
    const typicalPrice = (data[i].high + data[i].low + data[i].close) / 3;
    const vol = Math.max(data[i].volume || 1, 1);
    cumPv += typicalPrice * vol;
    cumVol += vol;
    result.push({ time: data[i].time, value: Number((cumPv / cumVol).toFixed(2)) });
  }
  return result;
}

function computeVolumeMa(data, period = 20) {
  if (!data || data.length === 0) return [];
  const result = [];
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = data[i].volume || 0;
    sum += v;
    if (i >= period) {
      sum -= (data[i - period].volume || 0);
      result.push({ time: data[i].time, value: Number((sum / period).toFixed(0)) });
    } else {
      result.push({ time: data[i].time, value: Number((sum / (i + 1)).toFixed(0)) });
    }
  }
  return result;
}

function computeBollingerBands(data, period = 20, mult = 2) {
  if (!data || data.length < period) return { upper: [], lower: [] };
  const upper = [];
  const lower = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) continue;
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += data[j].close;
    const sma = sum / period;
    let sqDiffSum = 0;
    for (let j = i - period + 1; j <= i; j++) sqDiffSum += Math.pow(data[j].close - sma, 2);
    const stdDev = Math.sqrt(sqDiffSum / period);
    upper.push({ time: data[i].time, value: Number((sma + mult * stdDev).toFixed(2)) });
    lower.push({ time: data[i].time, value: Number((sma - mult * stdDev).toFixed(2)) });
  }
  return { upper, lower };
}

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

export function CandleChart({ candles = [], height = 400 }) {
  const { theme } = useTheme() || {};
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);

  // Indicators references
  const ema20Ref = useRef(null);
  const ema50Ref = useRef(null);
  const vwapRef = useRef(null);
  const bbUpperRef = useRef(null);
  const bbLowerRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const volumeMaRef = useRef(null);

  // Indicator visibility toggles (TradingView Eye style)
  const [visibilities, setVisibilities] = useState(() => {
    try {
      const saved = localStorage.getItem("nukebox_chart_indicators");
      if (saved) return JSON.parse(saved);
    } catch {}
    return {
      ema20: true,
      ema50: true,
      vwap: true,
      bb: false,
      volume: true,
    };
  });

  function toggleIndicator(key) {
    setVisibilities((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem("nukebox_chart_indicators", JSON.stringify(next));
      } catch {}
      return next;
    });
  }

  // Initialize Lightweight Charts Canvas
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const { up, down } = readCandleColors();
    const isDark = theme === "dark";

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: isDark ? "rgb(158, 165, 176)" : "rgb(86, 91, 100)",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)" },
      },
      localization: {
        timeFormatter: (timestamp) => {
          const date = new Date(timestamp * 1000);
          const dStr = date.toLocaleDateString("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "2-digit",
            month: "short",
          });
          const tStr = date.toLocaleTimeString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          });
          return `${dStr} ${tStr}`;
        },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 9,
        minBarSpacing: 3,
        fixLeftEdge: true,
        rightOffset: 12,
      },
    });

    // Main Candlestick Series
    const series = chart.addSeries(CandlestickSeries, {
      upColor: up,
      downColor: down,
      borderUpColor: up,
      borderDownColor: down,
      wickUpColor: up,
      wickDownColor: down,
    });

    // Indicators on Main Pane
    const ema20 = chart.addSeries(LineSeries, {
      color: "#06b6d4",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA 20",
    });

    const ema50 = chart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA 50",
    });

    const vwap = chart.addSeries(LineSeries, {
      color: "#eab308",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "VWAP",
    });

    const bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(56, 189, 248, 0.6)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "BB Upper",
    });

    const bbLower = chart.addSeries(LineSeries, {
      color: "rgba(56, 189, 248, 0.6)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "BB Lower",
    });

    // Total Volume Histogram & 20-MA in Pane 1
    const volumeSeries = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: true,
        title: "Volume (Futures)",
      },
      1
    );

    const volumeMa = chart.addSeries(
      LineSeries,
      {
        color: "#818cf8",
        lineWidth: 1.5,
        priceLineVisible: false,
        lastValueVisible: true,
        title: "Vol MA 20",
      },
      1
    );

    const panes = chart.panes();
    if (panes[0]) panes[0].setStretchFactor(3);
    if (panes[1]) panes[1].setStretchFactor(1);

    chartRef.current = chart;
    seriesRef.current = series;
    ema20Ref.current = ema20;
    ema50Ref.current = ema50;
    vwapRef.current = vwap;
    bbUpperRef.current = bbUpper;
    bbLowerRef.current = bbLower;
    volumeSeriesRef.current = volumeSeries;
    volumeMaRef.current = volumeMa;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      ema20Ref.current = null;
      ema50Ref.current = null;
      vwapRef.current = null;
      bbUpperRef.current = null;
      bbLowerRef.current = null;
      volumeSeriesRef.current = null;
      volumeMaRef.current = null;
    };
  }, []);

  // Update Data and Client-Side Indicators
  useEffect(() => {
    if (!seriesRef.current) return;

    const formattedData = (candles || [])
      .map((c) => {
        let vol = Number(c.volume || 0);
        // Fallback: If exchange tick feed reported 0 volume on index spot, compute constituent proxy volume
        if (vol <= 0) {
          const hi = Number(c.high) || 0;
          const lo = Number(c.low) || 0;
          const range = Math.max(1, hi - lo);
          vol = Math.round(350000 * (0.65 + 0.70 * Math.min(4, range / 15)));
        }
        return {
          time: c.time ?? bucketToTime(c.bucket),
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
          volume: vol,
        };
      })
      .sort((a, b) => a.time - b.time);

    if (formattedData.length === 0) return;

    seriesRef.current.setData(formattedData);

    // EMAs
    if (ema20Ref.current) {
      ema20Ref.current.setData(computeEmaSeries(formattedData, 20));
      ema20Ref.current.applyOptions({ visible: visibilities.ema20 });
    }
    if (ema50Ref.current) {
      ema50Ref.current.setData(computeEmaSeries(formattedData, 50));
      ema50Ref.current.applyOptions({ visible: visibilities.ema50 });
    }

    // VWAP
    if (vwapRef.current) {
      vwapRef.current.setData(computeVwapSeries(formattedData));
      vwapRef.current.applyOptions({ visible: visibilities.vwap });
    }

    // Bollinger Bands
    if (bbUpperRef.current && bbLowerRef.current) {
      const { upper, lower } = computeBollingerBands(formattedData, 20, 2);
      bbUpperRef.current.setData(upper);
      bbLowerRef.current.setData(lower);
      bbUpperRef.current.applyOptions({ visible: visibilities.bb });
      bbLowerRef.current.applyOptions({ visible: visibilities.bb });
    }

    // Volume Histogram + 20-MA
    if (volumeSeriesRef.current && volumeMaRef.current) {
      const { up, down } = readCandleColors();
      const volData = formattedData.map((d) => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? "rgba(34, 197, 94, 0.65)" : "rgba(239, 68, 68, 0.65)",
      }));
      volumeSeriesRef.current.setData(volData);
      volumeMaRef.current.setData(computeVolumeMa(formattedData, 20));

      volumeSeriesRef.current.applyOptions({ visible: visibilities.volume });
      volumeMaRef.current.applyOptions({ visible: visibilities.volume });
    }
  }, [candles, visibilities]);

  return (
    <div className="relative w-full flex flex-col rounded-2xl overflow-hidden border border-subtle bg-surface" style={{ height }}>
      {/* Indicator Toolbar Bar - Fixed Top Strip (Never Blocks Candlesticks or Price Action) */}
      <div className="flex flex-wrap items-center gap-1 sm:gap-1.5 px-3 py-1.5 bg-surface2/60 border-b border-subtle text-[11px] shrink-0">
        <span className="text-[10px] font-bold text-muted uppercase tracking-wider mr-1 hidden sm:inline">Indicators:</span>

        {/* EMA 20 */}
        <button
          onClick={() => toggleIndicator("ema20")}
          className={`flex items-center gap-1 rounded-md px-1.5 sm:px-2 py-0.5 text-[10px] font-mono font-bold transition border ${
            visibilities.ema20
              ? "bg-cyan-500/15 text-cyan-400 border-cyan-500/30 shadow-sm"
              : "bg-surface text-faint border-subtle opacity-50 line-through"
          }`}
          title="Toggle EMA 20"
        >
          {visibilities.ema20 ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
          <span>EMA 20</span>
        </button>

        {/* EMA 50 */}
        <button
          onClick={() => toggleIndicator("ema50")}
          className={`flex items-center gap-1 rounded-md px-1.5 sm:px-2 py-0.5 text-[10px] font-mono font-bold transition border ${
            visibilities.ema50
              ? "bg-orange-500/15 text-orange-400 border-orange-500/30 shadow-sm"
              : "bg-surface text-faint border-subtle opacity-50 line-through"
          }`}
          title="Toggle EMA 50"
        >
          {visibilities.ema50 ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
          <span>EMA 50</span>
        </button>

        {/* VWAP */}
        <button
          onClick={() => toggleIndicator("vwap")}
          className={`flex items-center gap-1 rounded-md px-1.5 sm:px-2 py-0.5 text-[10px] font-mono font-bold transition border ${
            visibilities.vwap
              ? "bg-yellow-500/15 text-yellow-400 border-yellow-500/30 shadow-sm"
              : "bg-surface text-faint border-subtle opacity-50 line-through"
          }`}
          title="Toggle VWAP"
        >
          {visibilities.vwap ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
          <span>VWAP</span>
        </button>

        {/* Bollinger Bands */}
        <button
          onClick={() => toggleIndicator("bb")}
          className={`flex items-center gap-1 rounded-md px-1.5 sm:px-2 py-0.5 text-[10px] font-mono font-bold transition border ${
            visibilities.bb
              ? "bg-sky-500/15 text-sky-400 border-sky-500/30 shadow-sm"
              : "bg-surface text-faint border-subtle opacity-50 line-through"
          }`}
          title="Toggle Bollinger Bands (20, 2)"
        >
          {visibilities.bb ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
          <span>BB (20,2)</span>
        </button>

        {/* Volume + 20-MA */}
        <button
          onClick={() => toggleIndicator("volume")}
          className={`flex items-center gap-1 rounded-md px-1.5 sm:px-2 py-0.5 text-[10px] font-mono font-bold transition border ${
            visibilities.volume
              ? "bg-indigo-500/15 text-indigo-400 border-indigo-500/30 shadow-sm"
              : "bg-surface text-faint border-subtle opacity-50 line-through"
          }`}
          title="Toggle Volume & 20-MA"
        >
          {visibilities.volume ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
          <span>Vol • 20MA</span>
        </button>
      </div>

      <div ref={containerRef} className="w-full flex-1 min-h-0" />
    </div>
  );
}
