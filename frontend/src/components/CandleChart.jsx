import { useEffect, useRef, useState, useMemo } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CrosshairMode,
  LineStyle,
} from "lightweight-charts";
import { Eye, EyeOff, Magnet, Maximize2, Minimize2, ZoomIn } from "lucide-react";
import { useTheme } from "../contexts/ThemeContext";
import { getActivePalette } from "../utils/chartPalette";

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

export function CandleChart({ candles = [], trades = [], height = 400 }) {
  const { theme } = useTheme() || {};
  const isDark = theme === "dark";
  const containerRef = useRef(null);
  const chartWrapperRef = useRef(null);
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

  // Interactive UI state
  const [palette, setPalette] = useState(getActivePalette());
  const [isMagnet, setIsMagnet] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hoveredCandle, setHoveredCandle] = useState(null);

  // Indicator visibility toggles
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

  // Listen for palette updates from Settings Screen
  useEffect(() => {
    const handlePaletteChange = () => setPalette(getActivePalette());
    window.addEventListener("nukebox_palette_changed", handlePaletteChange);
    return () => window.removeEventListener("nukebox_palette_changed", handlePaletteChange);
  }, []);

  function toggleIndicator(key) {
    setVisibilities((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem("nukebox_chart_indicators", JSON.stringify(next));
      } catch {}
      return next;
    });
  }

  // Format candles safely
  const formattedData = useMemo(() => {
    return (candles || [])
      .map((c) => {
        let t = c.time;
        if (!t && c.timestamp) {
          t = Math.floor(new Date(c.timestamp).getTime() / 1000);
        }
        return {
          time: t,
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
          volume: Number(c.volume || 0),
        };
      })
      .filter((c) => !isNaN(c.time) && !isNaN(c.open) && !isNaN(c.close) && c.open > 0)
      .sort((a, b) => a.time - b.time);
  }, [candles]);

  const latestCandle = formattedData.length > 0 ? formattedData[formattedData.length - 1] : null;
  const activeDisplayCandle = hoveredCandle || latestCandle;

  // Initialize Lightweight Charts Canvas
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

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
      crosshair: {
        mode: isMagnet ? CrosshairMode.Magnet : CrosshairMode.Normal,
        vertLine: {
          color: isDark ? "rgba(255, 255, 255, 0.25)" : "rgba(0, 0, 0, 0.25)",
          width: 1,
          style: LineStyle.Dashed,
        },
        horzLine: {
          color: isDark ? "rgba(255, 255, 255, 0.25)" : "rgba(0, 0, 0, 0.25)",
          width: 1,
          style: LineStyle.Dashed,
        },
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
          return `${dStr} ${tStr} IST`;
        },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 9,
        minBarSpacing: 3,
        fixLeftEdge: true,
        rightOffset: 12,
        // Crucial fix: Format horizontal axis tick marks in Indian Standard Time (IST)
        tickMarkFormatter: (time, tickMarkType) => {
          const date = new Date(time * 1000);
          if (tickMarkType < 3) {
            return date.toLocaleDateString("en-IN", {
              timeZone: "Asia/Kolkata",
              day: "numeric",
              month: "short",
            });
          }
          return date.toLocaleTimeString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          });
        },
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: false,
        mouseWheel: true,
        pinch: true,
      },
      kineticScroll: {
        touch: true,
        mouse: false,
      },
    });

    // Main Candlestick Series
    const series = chart.addSeries(CandlestickSeries, {
      upColor: palette.upColor,
      downColor: palette.downColor,
      borderUpColor: palette.upColor,
      borderDownColor: palette.downColor,
      wickUpColor: palette.upColor,
      wickDownColor: palette.downColor,
    });

    // Indicators on Main Pane
    const ema20 = chart.addSeries(LineSeries, {
      color: palette.ema20Color,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA 20",
    });

    const ema50 = chart.addSeries(LineSeries, {
      color: palette.ema50Color,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA 50",
    });

    const vwap = chart.addSeries(LineSeries, {
      color: palette.vwapColor,
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "VWAP",
    });

    const bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(56, 189, 248, 0.6)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "BB Upper",
    });

    const bbLower = chart.addSeries(LineSeries, {
      color: "rgba(56, 189, 248, 0.6)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
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

    // Crosshair movement subscription for dynamic OHLCV HUD header
    chart.subscribeCrosshairMove((param) => {
      if (
        !param.time ||
        param.point === undefined ||
        param.point.x < 0 ||
        param.point.x > container.clientWidth ||
        param.point.y < 0 ||
        param.point.y > container.clientHeight
      ) {
        setHoveredCandle(null);
        return;
      }
      const candlePrice = param.seriesData.get(series);
      if (candlePrice) {
        const volData = param.seriesData.get(volumeSeries);
        const vwapData = param.seriesData.get(vwap);
        setHoveredCandle({
          open: candlePrice.open,
          high: candlePrice.high,
          low: candlePrice.low,
          close: candlePrice.close,
          volume: volData ? volData.value : null,
          vwap: vwapData ? vwapData.value : null,
          time: param.time,
        });
      }
    });

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
  }, [theme, isMagnet, palette]);

  // Update Data and Series
  useEffect(() => {
    if (!seriesRef.current || formattedData.length === 0) return;

    seriesRef.current.setData(formattedData);

    // EMA 20 & 50
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
      const volData = formattedData.map((d) => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? palette.volumeUp : palette.volumeDown,
      }));
      volumeSeriesRef.current.setData(volData);
      volumeMaRef.current.setData(computeVolumeMa(formattedData, 20));
      volumeSeriesRef.current.applyOptions({ visible: visibilities.volume });
      volumeMaRef.current.applyOptions({ visible: visibilities.volume });
    }

    // Interactive Trade Markers Overlay
    if (trades && trades.length > 0 && seriesRef.current) {
      const markers = trades
        .filter((t) => t.entry_time)
        .map((t) => {
          const entryTimeUnix = Math.floor(new Date(t.entry_time).getTime() / 1000);
          const isCE = (t.direction || "").toUpperCase() === "CE";
          return {
            time: entryTimeUnix,
            position: isCE ? "belowBar" : "aboveBar",
            color: isCE ? "#10b981" : "#f43f5e",
            shape: isCE ? "arrowUp" : "arrowDown",
            text: `${t.direction || "BUY"} @ ₹${Math.round(t.entry_price || 0)}`,
          };
        })
        .sort((a, b) => a.time - b.time);
      try {
        seriesRef.current.setMarkers(markers);
      } catch {}
    }
  }, [formattedData, visibilities, palette, trades]);

  // Quick Zoom Helper
  const handleQuickZoom = (range) => {
    if (!chartRef.current || formattedData.length === 0) return;
    const timeScale = chartRef.current.timeScale();
    const lastBarTime = formattedData[formattedData.length - 1].time;

    if (range === "all") {
      timeScale.fitContent();
      return;
    }

    let secondsBack = 86400; // 1 day
    if (range === "2d") secondsBack = 2 * 86400;
    else if (range === "5d") secondsBack = 5 * 86400;

    timeScale.setVisibleRange({
      from: lastBarTime - secondsBack,
      to: lastBarTime + 1800,
    });
  };

  const toggleFullscreen = () => {
    if (!chartWrapperRef.current) return;
    if (!document.fullscreenElement) {
      chartWrapperRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  const barChange = activeDisplayCandle
    ? activeDisplayCandle.close - activeDisplayCandle.open
    : 0;
  const barChangePct = activeDisplayCandle && activeDisplayCandle.open > 0
    ? (barChange / activeDisplayCandle.open) * 100
    : 0;
  const isBullish = barChange >= 0;

  return (
    <div
      ref={chartWrapperRef}
      className={`relative w-full flex flex-col rounded-2xl overflow-hidden border border-subtle bg-surface ${
        isFullscreen ? "p-4 fixed inset-0 z-50 rounded-none bg-surface" : ""
      }`}
      style={{ height: isFullscreen ? "100vh" : height }}
    >
      {/* 1. Dynamic Live OHLCV HUD Legend */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-surface2/80 border-b border-subtle text-xs font-mono select-none shrink-0">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          {activeDisplayCandle ? (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-faint uppercase font-bold">O:</span>
                <span className="font-bold text-primary">{activeDisplayCandle.open.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-faint uppercase font-bold">H:</span>
                <span className="font-bold text-primary">{activeDisplayCandle.high.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-faint uppercase font-bold">L:</span>
                <span className="font-bold text-primary">{activeDisplayCandle.low.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-faint uppercase font-bold">C:</span>
                <span className={`font-bold ${isBullish ? "text-bull" : "text-bear"}`}>
                  {activeDisplayCandle.close.toFixed(2)}
                </span>
                <span className={`text-[11px] font-bold ${isBullish ? "text-bull" : "text-bear"}`}>
                  ({isBullish ? "+" : ""}{barChangePct.toFixed(2)}%)
                </span>
              </div>
              {activeDisplayCandle.volume ? (
                <div className="hidden sm:flex items-center gap-1.5">
                  <span className="text-[10px] text-faint uppercase font-bold">Vol:</span>
                  <span className="font-bold text-muted">
                    {activeDisplayCandle.volume >= 1000000
                      ? `${(activeDisplayCandle.volume / 1000000).toFixed(2)}M`
                      : activeDisplayCandle.volume >= 1000
                      ? `${(activeDisplayCandle.volume / 1000).toFixed(1)}K`
                      : activeDisplayCandle.volume}
                  </span>
                </div>
              ) : null}
              {activeDisplayCandle.vwap ? (
                <div className="hidden md:flex items-center gap-1.5">
                  <span className="text-[10px] text-yellow-500 font-bold uppercase">VWAP:</span>
                  <span className="font-bold text-yellow-400">{activeDisplayCandle.vwap.toFixed(2)}</span>
                </div>
              ) : null}
            </>
          ) : (
            <span className="text-faint text-[11px]">Hover over candle to inspect OHLCV data</span>
          )}
        </div>

        {/* Quick Zoom Presets & Fullscreen */}
        <div className="flex items-center gap-1 sm:gap-2">
          <div className="flex items-center rounded-lg bg-surface/60 border border-subtle p-0.5 text-[10px]">
            <button
              onClick={() => handleQuickZoom("1d")}
              className="px-1.5 py-0.5 rounded text-faint hover:text-primary transition"
              title="Zoom Today"
            >
              1D
            </button>
            <button
              onClick={() => handleQuickZoom("2d")}
              className="px-1.5 py-0.5 rounded text-faint hover:text-primary transition"
              title="Zoom 2 Days"
            >
              2D
            </button>
            <button
              onClick={() => handleQuickZoom("5d")}
              className="px-1.5 py-0.5 rounded text-faint hover:text-primary transition"
              title="Zoom 5 Days"
            >
              5D
            </button>
            <button
              onClick={() => handleQuickZoom("all")}
              className="px-1.5 py-0.5 rounded text-faint hover:text-primary transition font-bold"
              title="Fit All"
            >
              All
            </button>
          </div>

          {/* Magnet Snapping Toggle */}
          <button
            onClick={() => setIsMagnet(!isMagnet)}
            className={`p-1 rounded-lg border transition ${
              isMagnet
                ? "bg-accent/15 text-accent border-accent/40 shadow-sm"
                : "bg-surface text-faint border-subtle hover:text-primary"
            }`}
            title={isMagnet ? "Magnet Mode: Snapping to OHLC (Click to Free)" : "Free Crosshair Mode (Click for Magnet)"}
          >
            <Magnet className="h-3 w-3" />
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={toggleFullscreen}
            className="p-1 rounded-lg border border-subtle bg-surface text-faint hover:text-primary transition"
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* 2. Indicator Toolbar Bar */}
      <div className="flex flex-wrap items-center gap-1 sm:gap-1.5 px-3 py-1 bg-surface2/40 border-b border-subtle text-[11px] shrink-0">
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
          title="Toggle Volume (Futures) & 20-MA"
        >
          {visibilities.volume ? <Eye className="h-2.5 w-2.5" /> : <EyeOff className="h-2.5 w-2.5" />}
          <span>Vol • 20MA</span>
        </button>
      </div>

      {/* 3. Canvas Container with Mobile Touch Distortion Fix */}
      <div
        ref={containerRef}
        className="w-full flex-1 min-h-0 select-none relative"
        style={{
          touchAction: "none",
          overscrollBehavior: "none",
          WebkitUserSelect: "none",
        }}
      />
    </div>
  );
}
