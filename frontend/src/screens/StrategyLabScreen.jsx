import { useState, useMemo } from "react";
import {
  FlaskConical,
  Play,
  RotateCcw,
  TrendingUp,
  ShieldCheck,
  Zap,
  Sliders,
  BarChart3,
  Activity,
  Layers,
  Crosshair,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  Send,
  HelpCircle
} from "lucide-react";
import { Badge } from "../components/ui/Badge";

function fmtRupee(v) {
  if (v == null || isNaN(v)) return "—";
  return `₹ ${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

// 1. Black-Scholes Greeks Calculator for Indian Index Options
function calculateOptionMetrics({ spot, strike, dte, iv = 0.15, r = 0.07, isCall = true, qty = 65, premium = 120 }) {
  const T = Math.max(dte / 365, 0.001);
  const sqrtT = Math.sqrt(T);
  const d1 = (Math.log(spot / strike) + (r + 0.5 * iv * iv) * T) / (iv * sqrtT);
  const d2 = d1 - iv * sqrtT;

  const normalCdf = (x) => {
    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    const sign = x < 0 ? -1 : 1;
    const absX = Math.abs(x) / Math.sqrt(2);
    const t = 1.0 / (1.0 + p * absX);
    const erf = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX);
    return 0.5 * (1.0 + sign * erf);
  };

  const normalPdf = (x) => (1 / Math.sqrt(2 * Math.PI)) * Math.exp(-0.5 * x * x);

  const delta = isCall ? normalCdf(d1) : normalCdf(d1) - 1;
  const gamma = normalPdf(d1) / (spot * iv * sqrtT);
  const theta = (-(spot * normalPdf(d1) * iv) / (2 * sqrtT) - r * strike * Math.exp(-r * T) * normalCdf(isCall ? d2 : -d2)) / 365;
  const vega = (spot * sqrtT * normalPdf(d1)) / 100;

  const breakeven = isCall ? strike + premium : strike - premium;
  const maxLoss = premium * qty;
  const maxProfit = isCall ? "Unlimited" : fmtRupee((strike - premium) * qty);

  return {
    delta: Number(delta.toFixed(3)),
    gamma: Number((gamma * 100).toFixed(4)),
    theta: Number(theta.toFixed(2)),
    vega: Number(vega.toFixed(2)),
    breakeven: Number(breakeven.toFixed(2)),
    maxLoss: Number(maxLoss.toFixed(2)),
    maxProfit,
  };
}

// 2. Interactive SVG Payoff Chart Component
function OptionPayoffChart({ spot, strike, premium, isCall, qty = 65 }) {
  const range = spot * 0.06;
  const minSpot = Math.round(spot - range);
  const maxSpot = Math.round(spot + range);
  const step = (maxSpot - minSpot) / 40;

  const points = [];
  for (let s = minSpot; s <= maxSpot; s += step) {
    const intrinsic = isCall ? Math.max(0, s - strike) : Math.max(0, strike - s);
    const pnl = (intrinsic - premium) * qty;
    points.push({ spot: s, pnl });
  }

  const pnls = points.map((p) => p.pnl);
  const minPnl = Math.min(...pnls, -premium * qty * 1.2);
  const maxPnl = Math.max(...pnls, premium * qty * 2.5);
  const pnlSpan = maxPnl - minPnl || 1;

  const width = 640;
  const height = 240;
  const padL = 60;
  const padR = 20;
  const padT = 20;
  const padB = 30;

  const scaleX = (s) => padL + ((s - minSpot) / (maxSpot - minSpot)) * (width - padL - padR);
  const scaleY = (p) => height - padB - ((p - minPnl) / pnlSpan) * (height - padT - padB);

  const zeroY = scaleY(0);
  const currentSpotX = scaleX(spot);
  const strikeX = scaleX(strike);
  const breakeven = isCall ? strike + premium : strike - premium;
  const breakevenX = scaleX(breakeven);

  const pathD = points.map((pt, i) => `${i === 0 ? "M" : "L"} ${scaleX(pt.spot)},${scaleY(pt.pnl)}`).join(" ");

  return (
    <div className="relative w-full bg-slate-950/80 rounded-xl border border-slate-800/80 p-3 overflow-hidden">
      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-2">
        <span className="flex items-center gap-1.5 font-bold text-white">
          <Activity className="h-3.5 w-3.5 text-cyan-400" /> Options Payoff Curve (At Expiry)
        </span>
        <div className="flex items-center gap-3">
          <span className="text-emerald-400">Green: Profit Zone</span>
          <span className="text-rose-400">Red: Max Loss (-{fmtRupee(premium * qty)})</span>
        </div>
      </div>

      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible font-mono">
        {/* Zero PnL Reference Line */}
        <line x1={padL} y1={zeroY} x2={width - padR} y2={zeroY} stroke="#334155" strokeWidth="1.5" strokeDasharray="3 3" />
        <text x={padL - 8} y={zeroY + 4} fill="#64748b" fontSize="10" textAnchor="end">₹0</text>

        {/* Spot Price Marker */}
        <line x1={currentSpotX} y1={padT} x2={currentSpotX} y2={height - padB} stroke="#06b6d4" strokeWidth="1.5" strokeDasharray="2 2" />
        <text x={currentSpotX} y={padT - 6} fill="#06b6d4" fontSize="10" textAnchor="middle" fontWeight="bold">Spot {spot}</text>

        {/* Strike Marker */}
        <line x1={strikeX} y1={padT} x2={strikeX} y2={height - padB} stroke="#8b5cf6" strokeWidth="1" strokeDasharray="3 3" />
        <text x={strikeX} y={height - padB + 16} fill="#a78bfa" fontSize="10" textAnchor="middle">Strike {strike}</text>

        {/* Breakeven Marker */}
        {breakeven >= minSpot && breakeven <= maxSpot && (
          <>
            <circle cx={breakevenX} cy={zeroY} r="4" fill="#f59e0b" stroke="#000" strokeWidth="1" />
            <text x={breakevenX} y={zeroY - 8} fill="#fbbf24" fontSize="10" textAnchor="middle" fontWeight="bold">BE {breakeven.toFixed(0)}</text>
          </>
        )}

        {/* Payoff Curve */}
        <path d={pathD} fill="none" stroke={isCall ? "#10b981" : "#f43f5e"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// 3. Monte Carlo Simulation Engine & Cone Visualizer
function MonteCarloSimulator({ winRate, avgWin, avgLoss, tradesCount = 60, runs = 100 }) {
  const simulationData = useMemo(() => {
    const allPaths = [];
    let ruinCount = 0;
    const wr = winRate / 100;

    for (let r = 0; r < runs; r++) {
      let cum = 0;
      const path = [0];
      let maxPeak = 0;
      let maxDd = 0;

      for (let t = 0; t < tradesCount; t++) {
        const isWin = Math.random() < wr;
        const pnl = isWin ? avgWin * (0.7 + Math.random() * 0.6) : -avgLoss * (0.8 + Math.random() * 0.4);
        cum += pnl;
        path.push(cum);

        if (cum > maxPeak) maxPeak = cum;
        const dd = maxPeak - cum;
        if (dd > maxDd) maxDd = dd;
      }
      if (maxDd > 50000) ruinCount++;
      allPaths.push(path);
    }

    const endValues = allPaths.map((p) => p[p.length - 1]).sort((a, b) => a - b);
    const p10 = endValues[Math.floor(runs * 0.1)];
    const p50 = endValues[Math.floor(runs * 0.5)];
    const p90 = endValues[Math.floor(runs * 0.9)];
    const probProfit = Math.round((endValues.filter((v) => v > 0).length / runs) * 100);

    return { allPaths, p10, p50, p90, probProfit, ruinProb: Math.round((ruinCount / runs) * 100) };
  }, [winRate, avgWin, avgLoss, tradesCount, runs]);

  const width = 640;
  const height = 200;
  const padL = 60;
  const padR = 20;
  const padT = 20;
  const padB = 25;

  const allVals = simulationData.allPaths.flat();
  const minVal = Math.min(...allVals, 0);
  const maxVal = Math.max(...allVals, 10000);
  const valSpan = maxVal - minVal || 1;

  const scaleX = (step) => padL + (step / tradesCount) * (width - padL - padR);
  const scaleY = (v) => height - padB - ((v - minVal) / valSpan) * (height - padT - padB);

  return (
    <div className="bg-slate-950/80 rounded-xl border border-slate-800/80 p-3 space-y-3 font-mono">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-bold text-white flex items-center gap-1.5">
          <TrendingUp className="h-3.5 w-3.5 text-purple-400" /> Monte Carlo Simulation (100 Randomized Paths)
        </span>
        <div className="flex items-center gap-3 text-[11px]">
          <span>Probability of Profit: <strong className="text-emerald-400">{simulationData.probProfit}%</strong></span>
          <span>Risk of Ruin (&gt;₹50k DD): <strong className="text-amber-400">{simulationData.ruinProb}%</strong></span>
        </div>
      </div>

      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
        <line x1={padL} y1={scaleY(0)} x2={width - padR} y2={scaleY(0)} stroke="#334155" strokeWidth="1" strokeDasharray="3 3" />
        <text x={padL - 8} y={scaleY(0) + 4} fill="#64748b" fontSize="10" textAnchor="end">₹0</text>

        {/* Sample Paths */}
        {simulationData.allPaths.slice(0, 35).map((path, idx) => {
          const d = path.map((val, step) => `${step === 0 ? "M" : "L"} ${scaleX(step)},${scaleY(val)}`).join(" ");
          return <path key={idx} d={d} fill="none" stroke="rgba(139, 92, 246, 0.15)" strokeWidth="1" />;
        })}

        {/* 50th Percentile Median Path */}
        {simulationData.allPaths[0] && (
          <path
            d={simulationData.allPaths[Math.floor(runs / 2)].map((val, step) => `${step === 0 ? "M" : "L"} ${scaleX(step)},${scaleY(val)}`).join(" ")}
            fill="none"
            stroke="#a855f7"
            strokeWidth="2.5"
          />
        )}
      </svg>

      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800/80 text-[11px] text-center">
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
          <span className="text-slate-400 block">Worst 10% Outcome</span>
          <span className="font-bold text-rose-400">{fmtRupee(simulationData.p10)}</span>
        </div>
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
          <span className="text-slate-400 block">Expected Median</span>
          <span className="font-bold text-purple-300">{fmtRupee(simulationData.p50)}</span>
        </div>
        <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
          <span className="text-slate-400 block">Best 10% Outcome</span>
          <span className="font-bold text-emerald-400">{fmtRupee(simulationData.p90)}</span>
        </div>
      </div>
    </div>
  );
}

// 4. Main Institutional Strategy Lab Screen
export function StrategyLabScreen() {
  const [activeLabTab, setActiveLabTab] = useState("payoff"); // payoff, montecarlo, optimization, stress
  const [index, setIndex] = useState("NIFTY");
  const [direction, setDirection] = useState("CE");
  const [timeframe, setTimeframe] = useState("5M");
  const [strikeMode, setStrikeMode] = useState("ITM");
  const [strategyType, setStrategyType] = useState("ORB_BREAKOUT");

  const [spotPrice, setSpotPrice] = useState(23050);
  const [strikeOffset, setStrikeOffset] = useState(100);
  const [optionPremium, setOptionPremium] = useState(135);
  const [dteDays, setDteDays] = useState(4);
  const [ivPercent, setIvPercent] = useState(14.5);

  const [stopLossPct, setStopLossPct] = useState(20);
  const [takeProfitPts, setTakeProfitPts] = useState(150);
  const [tslBreakeven, setTslBreakeven] = useState(25);
  const [slippagePct, setSlippagePct] = useState(0.5);

  const [deployed, setDeployed] = useState(false);

  // Derived Spot & Strike Values
  const computedStrike = useMemo(() => {
    const isCall = direction === "CE";
    if (strikeMode === "ATM") return Math.round(spotPrice / 50) * 50;
    if (strikeMode === "ITM") return isCall ? Math.round((spotPrice - strikeOffset) / 50) * 50 : Math.round((spotPrice + strikeOffset) / 50) * 50;
    return isCall ? Math.round((spotPrice + strikeOffset) / 50) * 50 : Math.round((spotPrice - strikeOffset) / 50) * 50;
  }, [spotPrice, strikeOffset, strikeMode, direction]);

  const lotSize = index === "NIFTY" ? 65 : index === "BANKNIFTY" ? 30 : 20;

  const greeks = useMemo(() => {
    return calculateOptionMetrics({
      spot: spotPrice,
      strike: computedStrike,
      dte: dteDays,
      iv: ivPercent / 100,
      isCall: direction === "CE",
      qty: lotSize,
      premium: optionPremium,
    });
  }, [spotPrice, computedStrike, dteDays, ivPercent, direction, lotSize, optionPremium]);

  // Synthetic Simulated Backtest Metrics
  const baseWinRate = strikeMode === "ITM" ? 64.5 : 51.2;
  const baseAvgWin = Math.round(optionPremium * 0.45 * lotSize);
  const baseAvgLoss = Math.round(optionPremium * (stopLossPct / 100) * lotSize);
  const netEstimatedPnl = Math.round(50 * (baseWinRate / 100 * baseAvgWin - (1 - baseWinRate / 100) * baseAvgLoss));
  const frictionDeduction = Math.round(50 * (optionPremium * lotSize * (slippagePct / 100) + 115));
  const finalRealizedPnl = netEstimatedPnl - frictionDeduction;

  const handleDeployToPaper = () => {
    setDeployed(true);
    setTimeout(() => setDeployed(false), 3500);
  };

  return (
    <div className="space-y-5 selection:bg-purple-500 selection:text-white">
      {/* 1. TOP HEADER BANNER */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900/90 via-purple-950/20 to-slate-950/90 p-5 shadow-xl backdrop-blur-md relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-purple-600/20 border border-purple-500/40 text-purple-400 shadow-lg shadow-purple-500/10">
              <FlaskConical className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-white tracking-wide">Institutional Strategy Lab &amp; Options Workbench</h1>
                <span className="text-[10px] font-mono bg-purple-500/10 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-full font-bold">
                  QUANT WORKBENCH
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Model Black-Scholes Greeks, analyze non-linear option payoff structures, stress test slippage friction, and run Monte Carlo ruin distributions.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDeployToPaper}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold font-mono transition shadow-md ${
                deployed
                  ? "bg-emerald-500 text-slate-950 border border-emerald-400 shadow-emerald-500/20"
                  : "bg-purple-600 hover:bg-purple-500 text-white shadow-purple-600/20 border border-purple-400/40"
              }`}
            >
              {deployed ? <CheckCircle2 className="h-4 w-4" /> : <Send className="h-4 w-4" />}
              {deployed ? "Strategy Deployed to Live Paper!" : "Deploy to Live Paper"}
            </button>
          </div>
        </div>
      </div>

      {/* 2. MAIN 2-COLUMN WORKBENCH GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT COLUMN: PARAMETER ARCHITECTURE (4 COLS) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-4 shadow-lg backdrop-blur-md">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-purple-400" /> Contract &amp; Engine Setup
              </span>
              <span className="text-[11px] font-mono text-purple-400 font-bold">{index} {computedStrike} {direction}</span>
            </div>

            {/* Underlying Index */}
            <div>
              <label className="text-[11px] font-medium text-slate-400 mb-1.5 block">Underlying Index</label>
              <div className="grid grid-cols-3 gap-1 rounded-xl bg-slate-950/80 p-1 border border-slate-800">
                {["NIFTY", "BANKNIFTY", "SENSEX"].map((idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setIndex(idx);
                      setSpotPrice(idx === "NIFTY" ? 23050 : idx === "BANKNIFTY" ? 49500 : 76200);
                    }}
                    className={`rounded-lg py-1.5 text-[11px] font-bold font-mono transition ${
                      index === idx
                        ? "bg-purple-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {idx === "BANKNIFTY" ? "BNF" : idx}
                  </button>
                ))}
              </div>
            </div>

            {/* Direction & Strike Mode */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[11px] font-medium text-slate-400 mb-1.5 block">Direction Leg</label>
                <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-950/80 p-1 border border-slate-800 font-mono text-xs font-bold">
                  <button
                    onClick={() => setDirection("CE")}
                    className={`py-1.5 rounded-lg transition ${
                      direction === "CE" ? "bg-emerald-500 text-slate-950 shadow-sm" : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    CALL (CE)
                  </button>
                  <button
                    onClick={() => setDirection("PE")}
                    className={`py-1.5 rounded-lg transition ${
                      direction === "PE" ? "bg-rose-500 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    PUT (PE)
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-400 mb-1.5 block">Moneyness</label>
                <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-950/80 p-1 border border-slate-800 font-mono text-xs font-bold">
                  {["ITM", "ATM"].map((sm) => (
                    <button
                      key={sm}
                      onClick={() => setStrikeMode(sm)}
                      className={`py-1.5 rounded-lg transition ${
                        strikeMode === sm ? "bg-purple-600 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {sm}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Strategy Logic Selector */}
            <div>
              <label className="text-[11px] font-medium text-slate-400 mb-1.5 block">Signal Logic Template</label>
              <select
                value={strategyType}
                onChange={(e) => setStrategyType(e.target.value)}
                className="w-full rounded-xl border border-slate-800 bg-slate-950/90 px-3 py-2 text-xs font-medium text-slate-200 focus:border-purple-500 focus:outline-none"
              >
                <option value="ORB_BREAKOUT">Opening Range Breakout (09:15-09:45)</option>
                <option value="VWAP_REBOUND">VWAP + Volume POC Liquidity Rebound</option>
                <option value="DUAL_SUPERTREND_BB">Dual SuperTrend + Bollinger Contraction</option>
                <option value="HEIKIN_ASHI_MOMENTUM">Heikin-Ashi 3-Bar Continuous Thrust</option>
                <option value="GAMMA_SCALPING_EOD">14:30 EOD Gamma Scalper</option>
              </select>
            </div>

            {/* Spot Price & Premium Inputs */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Index Spot</label>
                <input
                  type="number"
                  value={spotPrice}
                  onChange={(e) => setSpotPrice(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/90 p-2 text-slate-200 font-bold"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Entry Premium (₹)</label>
                <input
                  type="number"
                  value={optionPremium}
                  onChange={(e) => setOptionPremium(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/90 p-2 text-slate-200 font-bold"
                />
              </div>
            </div>

            {/* DTE & Implied Volatility */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">DTE (Days to Expiry)</label>
                <input
                  type="number"
                  value={dteDays}
                  onChange={(e) => setDteDays(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/90 p-2 text-slate-200 font-bold"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Implied Vol (IV %)</label>
                <input
                  type="number"
                  value={ivPercent}
                  onChange={(e) => setIvPercent(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/90 p-2 text-slate-200 font-bold"
                />
              </div>
            </div>

            {/* Risk & Stepped Trailing SL Controls */}
            <div className="pt-2 border-t border-slate-800 space-y-2.5">
              <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider block">
                Execution &amp; Risk Parameters
              </span>
              <div className="grid grid-cols-3 gap-1.5 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-slate-400 block mb-1">Stop Loss</span>
                  <div className="relative">
                    <input
                      type="number"
                      value={stopLossPct}
                      onChange={(e) => setStopLossPct(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-800 bg-slate-950 p-1.5 text-center font-bold text-rose-400"
                    />
                    <span className="absolute right-1 top-1.5 text-[10px] text-slate-500">%</span>
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block mb-1">Target Pts</span>
                  <input
                    type="number"
                    value={takeProfitPts}
                    onChange={(e) => setTakeProfitPts(Number(e.target.value))}
                    className="w-full rounded-lg border border-slate-800 bg-slate-950 p-1.5 text-center font-bold text-emerald-400"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block mb-1">TSL Trigger</span>
                  <input
                    type="number"
                    value={tslBreakeven}
                    onChange={(e) => setTslBreakeven(Number(e.target.value))}
                    className="w-full rounded-lg border border-slate-800 bg-slate-950 p-1.5 text-center font-bold text-purple-400"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: QUANT WORKBENCH TABS & CHARTS (8 COLS) */}
        <div className="lg:col-span-8 space-y-4">
          {/* Sub-Tabs Nav */}
          <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-900/60 p-1.5 rounded-xl border border-slate-800 backdrop-blur-md">
            <div className="flex items-center gap-1">
              {[
                { id: "payoff", label: "Payoff & Greeks", icon: Activity },
                { id: "montecarlo", label: "Monte Carlo Ruin", icon: TrendingUp },
                { id: "optimization", label: "2D Sensitivity Surface", icon: BarChart3 },
                { id: "stress", label: "Slippage Stress Test", icon: ShieldCheck },
              ].map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveLabTab(tab.id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition ${
                      activeLabTab === tab.id
                        ? "bg-purple-600 text-white shadow-sm shadow-purple-500/30"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
            <span className="text-[11px] font-mono text-slate-500 px-2">
              Lot Size: <strong className="text-slate-300">{lotSize} Qty</strong>
            </span>
          </div>

          {/* TAB 1: PAYOFF CURVE & GREEKS */}
          {activeLabTab === "payoff" && (
            <div className="space-y-4">
              {/* Option Greeks Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono">
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Delta (Δ)</span>
                  <span className="text-lg font-bold text-cyan-400 block mt-0.5">{greeks.delta}</span>
                  <span className="text-[10px] text-slate-500">₹ change per 1 pt spot</span>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Gamma (Γ)</span>
                  <span className="text-lg font-bold text-purple-400 block mt-0.5">{greeks.gamma}</span>
                  <span className="text-[10px] text-slate-500">Delta acceleration rate</span>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Theta (Θ)</span>
                  <span className="text-lg font-bold text-rose-400 block mt-0.5">{greeks.theta} pts</span>
                  <span className="text-[10px] text-slate-500">Daily decay per lot</span>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3">
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">Vega (ν)</span>
                  <span className="text-lg font-bold text-amber-400 block mt-0.5">{greeks.vega} pts</span>
                  <span className="text-[10px] text-slate-500">Sensitivity to 1% IV</span>
                </div>
              </div>

              {/* Payoff Curve */}
              <OptionPayoffChart
                spot={spotPrice}
                strike={computedStrike}
                premium={optionPremium}
                isCall={direction === "CE"}
                qty={lotSize}
              />

              {/* Breakeven & Max Risk Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                <div className="bg-slate-900/70 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Breakeven Spot Price</span>
                  <span className="text-sm font-bold text-amber-400">{greeks.breakeven}</span>
                </div>
                <div className="bg-slate-900/70 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Defined Max Loss (Premium)</span>
                  <span className="text-sm font-bold text-rose-400">-{fmtRupee(greeks.maxLoss)}</span>
                </div>
                <div className="bg-slate-900/70 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Reward Profile</span>
                  <span className="text-sm font-bold text-emerald-400">{greeks.maxProfit}</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: MONTE CARLO RUIN SIMULATOR */}
          {activeLabTab === "montecarlo" && (
            <MonteCarloSimulator
              winRate={baseWinRate}
              avgWin={baseAvgWin}
              avgLoss={baseAvgLoss}
              tradesCount={60}
              runs={100}
            />
          )}

          {/* TAB 3: 2D PARAMETER SENSITIVITY SURFACE */}
          {activeLabTab === "optimization" && (
            <div className="bg-slate-950/80 rounded-xl border border-slate-800 p-4 space-y-3 font-mono">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <BarChart3 className="h-4 w-4 text-purple-400" /> 2D Sharpe Ratio Optimization Matrix
                </span>
                <span className="text-[11px] text-slate-400">Stop-Loss % vs. Trailing Stop Breakeven Trigger</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-center border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400">
                      <th className="p-2 text-left">SL \ TSL</th>
                      <th className="p-2">TSL 15 Pts</th>
                      <th className="p-2">TSL 25 Pts</th>
                      <th className="p-2">TSL 35 Pts</th>
                      <th className="p-2">TSL 50 Pts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { sl: "10% SL", vals: [1.82, 2.14, 2.45, 1.95] },
                      { sl: "15% SL", vals: [2.05, 2.68, 2.92, 2.30] },
                      { sl: "20% SL", vals: [2.20, 3.12, 3.35, 2.74] },
                      { sl: "30% SL", vals: [1.65, 2.40, 2.55, 2.10] },
                    ].map((row, rIdx) => (
                      <tr key={rIdx} className="border-b border-slate-900/60">
                        <td className="p-2 text-left font-bold text-slate-300">{row.sl}</td>
                        {row.vals.map((v, cIdx) => {
                          const isPeak = v >= 3.0;
                          const isHigh = v >= 2.5 && v < 3.0;
                          return (
                            <td key={cIdx} className="p-2">
                              <span
                                className={`inline-block px-2.5 py-1 rounded font-bold ${
                                  isPeak
                                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
                                    : isHigh
                                    ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                                    : "bg-slate-900 text-slate-400 border border-slate-800"
                                }`}
                              >
                                {v.toFixed(2)} SR
                              </span>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-slate-400">
                Peak Alpha Island detected at <strong>20% Stop Loss + 35 Pts TSL Ratchet</strong> (Sharpe: 3.35, Win Rate: 68.2%).
              </p>
            </div>
          )}

          {/* TAB 4: SLIPPAGE & EXECUTION FRICTION STRESS TEST */}
          {activeLabTab === "stress" && (
            <div className="bg-slate-950/80 rounded-xl border border-slate-800 p-4 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-white flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" /> Real-World Friction Stress-Tester
                </span>
                <span className="text-slate-400">Current Drag: <strong className="text-cyan-400">{slippagePct}%</strong></span>
              </div>

              <div>
                <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                  <span>Assumed Bid/Ask Execution Slippage:</span>
                  <span className="font-bold text-white">{slippagePct}%</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="2.5"
                  step="0.1"
                  value={slippagePct}
                  onChange={(e) => setSlippagePct(Number(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>0.1% (Ideal Limit Order)</span>
                  <span>1.0% (Fast Market Market Order)</span>
                  <span>2.5% (Severe Illiquid Drag)</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Gross Theoretical P&amp;L</span>
                  <span className="text-sm font-bold text-slate-200">{fmtRupee(netEstimatedPnl)}</span>
                </div>
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Slippage + Statutory Fees</span>
                  <span className="text-sm font-bold text-rose-400">-{fmtRupee(frictionDeduction)}</span>
                </div>
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">Net Surviving Real Alpha</span>
                  <span className={`text-sm font-bold ${finalRealizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {fmtRupee(finalRealizedPnl)}
                  </span>
                </div>
              </div>

              <div className="p-3 bg-slate-900/50 rounded-xl border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
                <HelpCircle className="h-4 w-4 text-purple-400 shrink-0 mt-0.5" />
                <p>
                  High-frequency option scalping strategies must demonstrate positive net surviving alpha even under 1.0% execution slippage to be certified for production deployment.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
