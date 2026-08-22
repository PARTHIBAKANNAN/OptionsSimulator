import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck, Zap, Activity, Cpu, Sparkles, TrendingUp,
  BarChart3, ChevronRight, Lock, Mail, ArrowRight,
  Layers, CheckCircle2, Award, DollarSign, Calculator, Eye,
  Bot, Clock, HelpCircle, ArrowUpRight, ArrowDownRight, Globe
} from "lucide-react";

const STRATEGY_HIGHLIGHTS = [
  { name: "NIFTY Opening Range Breakout (5M ITM)", index: "NIFTY 50", tf: "5M", mode: "ITM", dir: "CE / PE", desc: "Captures morning opening momentum following the 09:15–09:30 range resolution with 1H 50-EMA trend alignment." },
  { name: "NIFTY 20-EMA Dynamic Bounce & Rejection", index: "NIFTY 50", tf: "5M", mode: "ITM", dir: "CE / PE", desc: "Trend-continuation pullbacks testing institutional exponential moving average supports on 5M timeframe." },
  { name: "NIFTY Heikin-Ashi Trend Continuation", index: "NIFTY 50", tf: "5M", mode: "ITM", dir: "CE / PE", desc: "Filtered smoothed trend riding with zero-wick directional momentum confirmation." },
  { name: "SENSEX Opening Range Breakout (5M ITM)", index: "SENSEX", tf: "5M", mode: "ITM", dir: "CE / PE", desc: "High-velocity breakout trading on BSE SENSEX 100-pt strike intervals." },
  { name: "SENSEX 20-EMA Bounce & Rejection", index: "SENSEX", tf: "5M", mode: "ITM", dir: "CE / PE", desc: "Systematic reversal and pullback entries aligned with 50-EMA macro trend." },
  { name: "SENSEX Stochastic Reversal Suite", index: "SENSEX", tf: "5M", mode: "ITM", dir: "CE / PE", desc: "Exhaustion bounce and rejection setups from oversold (20) and overbought (80) zones." },
  { name: "NIFTY 1M Momentum Scalper", index: "NIFTY 50", tf: "1M", mode: "ATM", dir: "CE / PE", desc: "Sub-minute momentum scalps capturing quick explosive volatility expansions." },
  { name: "SENSEX 1M Momentum Scalper", index: "SENSEX", tf: "1M", mode: "ATM", dir: "CE / PE", desc: "High-frequency ATM scalps executed within strict risk and time constraints." },
];

function fmtNum(v) {
  return v == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function LandingScreen({ onLoginClick }) {
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [sliderPts, setSliderPts] = useState(45);
  const [entryPrice, setEntryPrice] = useState(200);
  const [exitPrice, setExitPrice] = useState(245);
  const [lotQty, setLotQty] = useState(65);
  const [marketData, setMarketData] = useState(null);

  useEffect(() => {
    fetch("/api/public/market-summary")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setMarketData(d);
      })
      .catch(() => {});
  }, []);

  // Stepped TSL Simulation Math
  let tslStatus = "Initial Stop Loss (-20%) Active";
  let tslColor = "text-faint";
  let lockedProfit = "₹0 Guaranteed";
  if (sliderPts >= 60) {
    tslStatus = "Step 3 Locked (+40 pt Profit)";
    tslColor = "text-purple-400";
    lockedProfit = "+40 pts (+₹2,600 / Lot)";
  } else if (sliderPts >= 40) {
    tslStatus = "Step 2 Locked (+20 pt Profit)";
    tslColor = "text-emerald-400";
    lockedProfit = "+20 pts (+₹1,300 / Lot)";
  } else if (sliderPts >= 20) {
    tslStatus = "Step 1 Locked (Break-Even)";
    tslColor = "text-cyan-400";
    lockedProfit = "₹0 Risk (Break-Even)";
  }

  // Tax Calculator Math (Indian Regulatory Schedule)
  const turnoverBuy = entryPrice * lotQty;
  const turnoverSell = exitPrice * lotQty;
  const grossPnl = (exitPrice - entryPrice) * lotQty;
  const brokerage = 40.0; // ₹20 Buy + ₹20 Sell
  const stt = turnoverSell * 0.001; // 0.1% on Sell
  const excTurnover = (turnoverBuy + turnoverSell) * 0.0005; // 0.05%
  const gst = (brokerage + excTurnover) * 0.18; // 18% GST
  const sebiFee = ((turnoverBuy + turnoverSell) / 10000000) * 10;
  const stampDuty = turnoverBuy * 0.00003;
  const totalCharges = brokerage + stt + excTurnover + gst + sebiFee + stampDuty;
  const netPnl = grossPnl - totalCharges;

  const filteredStrats = STRATEGY_HIGHLIGHTS.filter((s) => {
    if (activeFilter === "NIFTY") return s.index.includes("NIFTY");
    if (activeFilter === "SENSEX") return s.index.includes("SENSEX");
    if (activeFilter === "5M") return s.tf === "5M";
    if (activeFilter === "1M") return s.tf === "1M";
    return true;
  });

  return (
    <div className="min-h-screen bg-bgDark text-primary selection:bg-accent selection:text-white font-sans overflow-x-hidden">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 border-b border-subtle/80 bg-bgDark/90 backdrop-blur-2xl px-4 sm:px-8 py-3.5">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-tr from-accent to-indigo-500 text-white font-black text-lg shadow-lg shadow-accent/25">
              OS
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-sm tracking-tight text-white">OptionsSimulator</span>
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[9px] font-extrabold text-emerald-400 border border-emerald-500/30 font-mono">
                  v2.5 Institutional
                </span>
              </div>
              <p className="text-[10px] text-faint font-medium">Quantitative Derivatives Execution Platform</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="mailto:parthiban.kannan@optionssimulator.internal?subject=Access%20Request%20for%20OptionsSimulator%20Quant%20Terminal"
              className="hidden sm:flex items-center gap-1.5 rounded-xl border border-subtle bg-surface2 px-3.5 py-2 text-xs font-bold text-muted hover:bg-surface3 hover:text-white transition"
            >
              <Mail className="h-3.5 w-3.5 text-accent" />
              <span>Request Access</span>
            </a>

            <button
              onClick={onLoginClick}
              className="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-black text-white hover:brightness-110 shadow-lg shadow-accent/25 transition"
            >
              <Lock className="h-3.5 w-3.5" />
              <span>Launch Terminal</span>
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section with Cinematic Background */}
      <section className="relative overflow-hidden pt-16 pb-20 px-4 sm:px-8 border-b border-subtle/40">
        {/* Background Image with Dark Vignette Overlay */}
        <div
          className="absolute inset-0 bg-cover bg-center opacity-25 mix-blend-luminosity pointer-events-none"
          style={{ backgroundImage: "url('/assets/quant_hero_bg.jpg')" }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-bgDark/40 via-bgDark/80 to-bgDark pointer-events-none" />

        <div className="mx-auto max-w-5xl text-center space-y-6 relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-1.5 text-xs font-bold text-accent shadow-sm backdrop-blur-md"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Institutional Options Derivatives Execution &amp; Risk Modeling Sandbox</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-tight"
          >
            Autonomous Index Options <br />
            <span className="bg-gradient-to-r from-cyan-400 via-accent to-purple-400 bg-clip-text text-transparent">
              Precision Quantitative Terminal
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mx-auto max-w-2xl text-sm sm:text-base text-gray-300 leading-relaxed font-sans"
          >
            A high-performance algorithmic execution engine for NSE NIFTY 50 and BSE SENSEX derivatives. Engineered with 21 multi-timeframe models, dynamic Delta strike targeting (Delta ≈ 0.60), multi-tier stepped profit locks, and AI market briefings.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-wrap items-center justify-center gap-3 pt-2"
          >
            <button
              onClick={onLoginClick}
              className="flex items-center gap-2 rounded-2xl bg-accent px-6 py-3.5 text-sm font-black text-white hover:brightness-110 shadow-xl shadow-accent/30 transition transform hover:-translate-y-0.5"
            >
              <span>Launch Operator Terminal</span>
              <ArrowRight className="h-4 w-4" />
            </button>
            <a
              href="#strategies"
              className="flex items-center gap-2 rounded-2xl border border-subtle bg-surface2/80 px-5 py-3.5 text-sm font-bold text-gray-300 hover:bg-surface3 hover:text-white backdrop-blur-sm transition"
            >
              <Eye className="h-4 w-4 text-cyan-400" />
              <span>Explore 21 Strategies</span>
            </a>
          </motion.div>

          {/* Real-Time Live Ticker Strip */}
          <div className="pt-8 max-w-3xl mx-auto">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-2xl border border-subtle bg-surface/80 backdrop-blur-xl">
              {/* NIFTY Ticker */}
              <div className="flex items-center justify-between px-4 py-2 rounded-xl bg-surface2/60 border border-subtle">
                <div className="text-left">
                  <span className="text-[10px] font-bold uppercase text-cyan-400 tracking-wider">NSE NIFTY 50 (Lot 65)</span>
                  <div className="font-mono text-lg font-black text-white tabular-nums">
                    {fmtNum(marketData?.nifty_price || 24120.0)}
                  </div>
                </div>
                <span className="rounded-full bg-bull/15 px-2.5 py-1 text-[11px] font-bold text-bull border border-bull/30 font-mono">
                  +{fmtNum(marketData?.nifty_change || 120.0)} (+{Number(marketData?.nifty_change_pct || 0.50).toFixed(2)}%)
                </span>
              </div>

              {/* SENSEX Ticker */}
              <div className="flex items-center justify-between px-4 py-2 rounded-xl bg-surface2/60 border border-subtle">
                <div className="text-left">
                  <span className="text-[10px] font-bold uppercase text-purple-400 tracking-wider">BSE SENSEX (Lot 20)</span>
                  <div className="font-mono text-lg font-black text-white tabular-nums">
                    {fmtNum(marketData?.sensex_price || 77540.83)}
                  </div>
                </div>
                <span className="rounded-full bg-bull/15 px-2.5 py-1 text-[11px] font-bold text-bull border border-bull/30 font-mono">
                  +{fmtNum(marketData?.sensex_change || 3.11)} (+{Number(marketData?.sensex_change_pct || 0.00).toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6 Key Architectural Pillars */}
      <section className="py-16 px-4 sm:px-8 max-w-7xl mx-auto space-y-6">
        <div className="text-center space-y-2 mb-10">
          <h2 className="text-2xl sm:text-3xl font-black text-white">Engineered for Quantitative Excellence</h2>
          <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
            Combining mathematical precision, high-speed tick processing, and institutional risk guardrails.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <div className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-500/15 text-cyan-400 border border-cyan-500/20">
              <Cpu className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">Delta-Optimized Strike Engine</h3>
            <p className="text-xs text-gray-400 leading-relaxed font-sans">
              Calculates Black-Scholes Greeks (Delta, Gamma, Theta, Vega) dynamically, targeting contracts with Delta ≈ 0.60 - 0.65 for rapid point velocity.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-purple-500/15 text-purple-400 border border-purple-500/20">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">Multi-Tier Stepped TSL</h3>
            <p className="text-xs text-gray-400 leading-relaxed font-sans">
              Automated ratchet stops: $+20\text{ pt}$ locks break-even, $+40\text{ pt}$ locks $+20\text{ pt}$, and $+60\text{ pt}$ locks $+40\text{ pt}$ profit without emotional interference.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
              <Bot className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">Dual AI Market Intelligence</h3>
            <p className="text-xs text-gray-400 leading-relaxed font-sans">
              08:50 AM Pre-Market Catalyst synthesis across global financial news + 15:35 IST automated post-market trade debrief and discipline auditing.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-500/15 text-rose-400 border border-rose-500/20">
              <Zap className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">₹5,000 Hard Loss Circuit Breaker</h3>
            <p className="text-xs text-gray-400 leading-relaxed font-sans">
              Strict intraday capital protection halts trading automatically if total daily realized or unrealized drawdown hits the configured threshold.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-400 border border-amber-500/20">
              <Clock className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">120-Minute Holding Limit</h3>
            <p className="text-xs text-gray-400 leading-relaxed font-sans">
              Eliminates midday sideways theta decay by automatically squaring off stagnant positions that exceed maximum intraday duration.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/20">
              <Activity className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-white">Signed Cumulative Volume Delta</h3>
            <p className="text-xs text-gray-400 leading-relaxed font-sans">
              Tick-by-tick order flow analysis tracks institutional buyer vs seller aggression at key support and resistance pivot levels.
            </p>
          </div>
        </div>
      </section>

      {/* Interactive Stepped TSL Simulator Widget */}
      <section className="py-16 px-4 sm:px-8 border-t border-subtle/60 bg-surface2/20 relative">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-purple-500/10 px-3 py-1 text-xs font-bold text-purple-400 border border-purple-500/20">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Interactive Profit Protection Demo</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white">Stepped Trailing Stop Loss (TSL) Simulator</h2>
            <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
              Drag the slider below to simulate live option point gains and observe how our multi-tier ratchet locks in guaranteed profit steps.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/90 p-6 sm:p-8 backdrop-blur-xl space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-faint">Simulated Points Gained</span>
                <div className="font-mono text-3xl sm:text-4xl font-black text-emerald-400">+{sliderPts} Points</div>
              </div>

              <div className="text-right">
                <span className="text-[10px] font-bold uppercase tracking-wider text-faint">Guaranteed Protection</span>
                <div className={`font-mono text-lg sm:text-xl font-bold ${tslColor}`}>{lockedProfit}</div>
                <div className="text-[11px] text-faint mt-0.5">{tslStatus}</div>
              </div>
            </div>

            {/* Slider */}
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              value={sliderPts}
              onChange={(e) => setSliderPts(Number(e.target.value))}
              className="w-full h-2.5 bg-surface3 rounded-lg appearance-none cursor-pointer accent-accent"
            />

            {/* Visual Milestones */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className={`p-3 rounded-2xl border ${sliderPts >= 0 ? "bg-surface2 border-subtle text-gray-300" : "bg-surface3/30 border-subtle/30 text-faint"}`}>
                <div className="text-[10px] uppercase font-bold text-faint">0 to +19 pts</div>
                <div className="font-bold text-white mt-1">Initial Entry</div>
                <div className="text-[10px] text-rose-400 mt-0.5">-20% Stop Loss</div>
              </div>

              <div className={`p-3 rounded-2xl border ${sliderPts >= 20 ? "bg-cyan-950/20 border-cyan-500/40 text-cyan-400" : "bg-surface3/30 border-subtle/30 text-faint"}`}>
                <div className="text-[10px] uppercase font-bold text-faint">+20 pt Milestone</div>
                <div className="font-bold text-white mt-1">Step 1 Lock</div>
                <div className="text-[10px] text-cyan-400 mt-0.5">SL = Entry (₹0 Risk)</div>
              </div>

              <div className={`p-3 rounded-2xl border ${sliderPts >= 40 ? "bg-emerald-950/20 border-emerald-500/40 text-emerald-400" : "bg-surface3/30 border-subtle/30 text-faint"}`}>
                <div className="text-[10px] uppercase font-bold text-faint">+40 pt Milestone</div>
                <div className="font-bold text-white mt-1">Step 2 Lock</div>
                <div className="text-[10px] text-emerald-400 mt-0.5">SL = +20 pt Profit</div>
              </div>

              <div className={`p-3 rounded-2xl border ${sliderPts >= 60 ? "bg-purple-950/20 border-purple-500/40 text-purple-400" : "bg-surface3/30 border-subtle/30 text-faint"}`}>
                <div className="text-[10px] uppercase font-bold text-faint">+60 pt Milestone</div>
                <div className="font-bold text-white mt-1">Step 3 Lock</div>
                <div className="text-[10px] text-purple-400 mt-0.5">SL = +40 pt Profit</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 21-Strategy Fleet Overview */}
      <section id="strategies" className="py-16 px-4 sm:px-8 max-w-7xl mx-auto space-y-8">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3 py-1 text-xs font-bold text-accent border border-accent/20">
            <Layers className="h-3.5 w-3.5" />
            <span>Quantitative Model Fleet</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black text-white">21 Algorithmic Strategies</h2>
          <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
            Systematic, non-discretionary execution models engineered specifically for Indian equity index derivatives microstructure.
          </p>

          {/* Filter Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
            {["ALL", "NIFTY", "SENSEX", "5M", "1M"].map((f) => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`rounded-xl px-4 py-1.5 text-xs font-bold transition border ${
                  activeFilter === f
                    ? "bg-accent text-white border-accent shadow-md shadow-accent/25"
                    : "bg-surface2 text-gray-400 border-subtle hover:text-white"
                }`}
              >
                {f === "ALL" ? "All Strategies" : f}
              </button>
            ))}
          </div>
        </div>

        {/* Strategy Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {filteredStrats.map((s, idx) => (
            <div key={idx} className="rounded-2xl border border-subtle bg-surface/80 p-5 space-y-3 hover:border-accent/40 transition">
              <div className="flex items-center justify-between">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-black border ${
                  s.index.includes("NIFTY") ? "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" : "bg-purple-500/15 text-purple-400 border-purple-500/30"
                }`}>
                  {s.index}
                </span>
                <span className="text-[10px] font-mono font-bold text-faint">{s.tf} • {s.mode}</span>
              </div>
              <h3 className="text-sm font-bold text-white tracking-tight">{s.name}</h3>
              <p className="text-xs text-gray-400 leading-relaxed font-sans">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Interactive Indian Regulatory Tax & Charges Calculator */}
      <section className="py-16 px-4 sm:px-8 border-t border-subtle/60 bg-surface2/20">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/20">
              <Calculator className="h-3.5 w-3.5" />
              <span>Real-Time Statutory Deduction Schedule</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white">Indian Regulatory Tax Calculator</h2>
            <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
              Our simulator accurately calculates statutory taxes in real time so your paper P&amp;L reflects actual take-home returns.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 rounded-3xl border border-subtle bg-surface/90 p-6 sm:p-8 backdrop-blur-xl">
            {/* Inputs */}
            <div className="space-y-4 font-sans text-xs">
              <h3 className="font-bold text-sm text-white">Trade Inputs</h3>
              <div>
                <label className="text-faint text-[11px] block mb-1">Buy Premium (₹)</label>
                <input
                  type="number"
                  value={entryPrice}
                  onChange={(e) => setEntryPrice(Number(e.target.value))}
                  className="w-full rounded-xl border border-subtle bg-surface2 px-3 py-2 text-xs font-mono font-bold text-primary"
                />
              </div>
              <div>
                <label className="text-faint text-[11px] block mb-1">Sell Premium (₹)</label>
                <input
                  type="number"
                  value={exitPrice}
                  onChange={(e) => setExitPrice(Number(e.target.value))}
                  className="w-full rounded-xl border border-subtle bg-surface2 px-3 py-2 text-xs font-mono font-bold text-primary"
                />
              </div>
              <div>
                <label className="text-faint text-[11px] block mb-1">Quantity (Units)</label>
                <input
                  type="number"
                  value={lotQty}
                  onChange={(e) => setLotQty(Number(e.target.value))}
                  className="w-full rounded-xl border border-subtle bg-surface2 px-3 py-2 text-xs font-mono font-bold text-primary"
                />
              </div>
            </div>

            {/* Breakdown */}
            <div className="space-y-2 text-xs font-mono border-y lg:border-y-0 lg:border-x border-subtle py-4 lg:py-0 lg:px-6">
              <h3 className="font-bold text-sm text-white font-sans mb-3">Itemized Regulatory Split</h3>
              <div className="flex justify-between text-gray-300">
                <span className="text-faint font-sans">Brokerage:</span>
                <span>₹{brokerage.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-300">
                <span className="text-faint font-sans">STT (0.1% on Sell):</span>
                <span>₹{stt.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-300">
                <span className="text-faint font-sans">Exchange Turnover:</span>
                <span>₹{excTurnover.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-300">
                <span className="text-faint font-sans">GST (18% on fees):</span>
                <span>₹{gst.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-300">
                <span className="text-faint font-sans">SEBI Turnover Fee:</span>
                <span>₹{sebiFee.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-gray-300">
                <span className="text-faint font-sans">Stamp Duty:</span>
                <span>₹{stampDuty.toFixed(2)}</span>
              </div>
              <div className="flex justify-between font-bold text-rose-400 border-t border-subtle pt-2">
                <span className="font-sans">Total Charges:</span>
                <span>₹{totalCharges.toFixed(2)}</span>
              </div>
            </div>

            {/* Net Output */}
            <div className="flex flex-col justify-center space-y-4 text-center p-4 rounded-2xl bg-surface2/60 border border-subtle">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-faint">Gross Realized P&amp;L</span>
                <div className="font-mono text-2xl font-bold text-gray-200">
                  {grossPnl >= 0 ? "+" : ""}₹{grossPnl.toFixed(2)}
                </div>
              </div>
              <div className="border-t border-subtle pt-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Net Take-Home P&amp;L</span>
                <div className={`font-mono text-3xl font-black ${netPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {netPnl >= 0 ? "+" : ""}₹{netPnl.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer & Compliance Disclaimer */}
      <footer className="border-t border-subtle bg-surface py-10 px-4 sm:px-8 text-xs text-faint">
        <div className="mx-auto max-w-7xl space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-accent" />
              <span className="font-bold text-primary">OptionsSimulator Technologies</span>
            </div>
            <div className="flex items-center gap-4">
              <a
                href="mailto:parthiban.kannan@optionssimulator.internal?subject=Access%20Request%20for%20OptionsSimulator%20Quant%20Terminal"
                className="font-bold text-accent hover:underline"
              >
                Request Operator Access
              </a>
              <span>•</span>
              <button onClick={onLoginClick} className="font-bold text-primary hover:underline">
                Operator Sign In
              </button>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed text-gray-400">
            <strong>Regulatory &amp; Compliance Notice:</strong> OptionsSimulator is an advanced simulated quantitative paper-trading and derivatives research platform. All orders, executions, and P&amp;L calculations are strictly modeled within a deterministic sandbox with zero real-capital routing. Designed for quantitative strategy validation, risk management modeling, and execution research under Indian regulatory parameters.
          </p>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-subtle/50 text-[10px]">
            <span>© 2026 OptionsSimulator Technologies. All Rights Reserved.</span>
            <span>NSE NIFTY 50 (Lot 65) • BSE SENSEX (Lot 20)</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
