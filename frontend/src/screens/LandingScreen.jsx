import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck, Zap, Activity, Cpu, Sparkles, TrendingUp,
  BarChart3, ChevronRight, Lock, Mail, ArrowRight,
  Layers, CheckCircle2, Award, DollarSign, Calculator, Eye,
  Bot, Clock, HelpCircle, ArrowUpRight, ArrowDownRight, Globe,
  Sliders, Play, X, ExternalLink, RefreshCw, Terminal
} from "lucide-react";
import { NukeBoxLogo } from "../components/NukeBoxLogo";
import { API_BASE } from "../lib/apiBase";

// 21 Proprietary Algorithmic Strategies (Formulas masked for IP protection)
const FLEET_21_STRATEGIES = [
  { id: "NIFTY_ORB_BULLISH_5M_ITM", name: "NIFTY Opening Range Momentum CE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.62", dir: "CE", desc: "Captures morning opening expansion following initial price discovery with macro trend filter alignment." },
  { id: "NIFTY_ORB_BEARISH_5M_ITM", name: "NIFTY Opening Range Breakdown PE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.62", dir: "PE", desc: "Executes directional downside breakdowns on expanding negative order flow velocity." },
  { id: "NIFTY_EMA_BOUNCE_5M_ITM", name: "NIFTY Dynamic Support Pullback CE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.60", dir: "CE", desc: "Enters high-probability trend continuation pullbacks testing institutional dynamic support levels." },
  { id: "NIFTY_EMA_REJECTION_5M_ITM", name: "NIFTY Dynamic Resistance Rejection PE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.60", dir: "PE", desc: "Capitalizes on overhead resistance rejections aligned with higher-timeframe bearish momentum." },
  { id: "NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM", name: "NIFTY Directional Trend Pulse CE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.64", dir: "CE", desc: "Smoothed noise-filtered trend-following model capturing multi-candle directional thrusts." },
  { id: "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", name: "NIFTY Directional Trend Pulse PE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.64", dir: "PE", desc: "Rides sustained downward momentum pulses with zero-shadow candle confirmation." },
  { id: "NIFTY_STOCHASTIC_BOUNCE_5M_ITM", name: "NIFTY Oversold Exhaustion Reversal CE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.58", dir: "CE", desc: "Exploits short-term oversold exhaustion bounces within primary uptrend regimes." },
  { id: "NIFTY_STOCHASTIC_REJECTION_5M_ITM", name: "NIFTY Overbought Exhaustion Reversal PE", index: "NIFTY 50", tf: "5M", mode: "ITM", targetDelta: "0.58", dir: "PE", desc: "Captures rapid mean-reversion rejections from extended overbought supply zones." },
  { id: "NIFTY_1M_SCALP_CE", name: "NIFTY High-Velocity Micro Scalp CE", index: "NIFTY 50", tf: "1M", mode: "ATM", targetDelta: "0.50", dir: "CE", desc: "Sub-minute momentum scalping engine exploiting instantaneous tick liquidity bursts." },
  { id: "NIFTY_1M_SCALP_PE", name: "NIFTY High-Velocity Micro Scalp PE", index: "NIFTY 50", tf: "1M", mode: "ATM", targetDelta: "0.50", dir: "PE", desc: "High-frequency downside scalps executed within strict risk and time constraints." },

  { id: "SENSEX_ORB_BULLISH_5M_ITM", name: "SENSEX Index Breakout Expansion CE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.62", dir: "CE", desc: "High-velocity breakout model calibrated for BSE SENSEX 100-point strike spacing." },
  { id: "SENSEX_ORB_BEARISH_5M_ITM", name: "SENSEX Index Breakdown Expansion PE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.62", dir: "PE", desc: "Captures rapid morning panic breakdowns on 30-share heavyweight index components." },
  { id: "SENSEX_EMA_BOUNCE_5M_ITM", name: "SENSEX Structural Support Pullback CE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.60", dir: "CE", desc: "Systematic pullback entries at structural moving average confluence zones." },
  { id: "SENSEX_EMA_REJECTION_5M_ITM", name: "SENSEX Structural Resistance Rejection PE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.60", dir: "PE", desc: "Downside rejection execution testing downward-sloping institutional resistance." },
  { id: "SENSEX_HEIKIN_ASHI_BULLISH_5M_ITM", name: "SENSEX Smoothed Trend Flow CE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.64", dir: "CE", desc: "Filters erratic intraday wicks to lock onto institutional multi-bar trend runs." },
  { id: "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", name: "SENSEX Smoothed Trend Flow PE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.64", dir: "PE", desc: "Bearish trend extension model with automated stepped trailing profit locks." },
  { id: "SENSEX_STOCHASTIC_BOUNCE_5M_ITM", name: "SENSEX Liquidity Sweep Reversal CE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.58", dir: "CE", desc: "Trades sharp liquidity sweep reversals from extreme oversold conditions." },
  { id: "SENSEX_STOCHASTIC_REJECTION_5M_ITM", name: "SENSEX Liquidity Sweep Rejection PE", index: "SENSEX", tf: "5M", mode: "ITM", targetDelta: "0.58", dir: "PE", desc: "Reversal model executing on false breakouts at session resistance." },
  { id: "SENSEX_1M_SCALP_CE", name: "SENSEX High-Frequency Micro Scalp CE", index: "SENSEX", tf: "1M", mode: "ATM", targetDelta: "0.50", dir: "CE", desc: "Rapid ATM scalp capture on explosive 1-minute volume surges." },
  { id: "SENSEX_1M_SCALP_PE", name: "SENSEX High-Frequency Micro Scalp PE", index: "SENSEX", tf: "1M", mode: "ATM", targetDelta: "0.50", dir: "PE", desc: "Fast-reacting ATM PE scalp with deterministic stop loss guardrails." },
  { id: "SENSEX_ATM_VOLATILITY_EXPANSION", name: "SENSEX Volatility Surge Model", index: "SENSEX", tf: "1M", mode: "ATM", targetDelta: "0.52", dir: "CE / PE", desc: "Captures sudden expansion in implied volatility around macroeconomic events." }
];

// Interactive Market Regimes Simulation Scenarios
const MARKET_REGIMES = [
  {
    id: "morning_surge",
    title: "09:15–10:00 Morning Surge",
    subtitle: "High Conviction Opening Momentum",
    tag: "Volatile Expansion",
    color: "from-cyan-500/20 to-blue-500/10 border-cyan-500/30 text-cyan-400",
    strikeDelta: "Δ ≈ 0.65 ITM (+1 Strike)",
    activeModels: "5M High-Conviction ORB",
    riskStatus: "Initial -20% Stop Loss Active",
    aiBriefing: "08:50 AM Pre-Market Catalyst detected positive GIFT Nifty delta (+85 pts) with banking sector accumulation.",
    expectedPoints: "+35 to +50 pts Target",
  },
  {
    id: "midday_chop",
    title: "11:30–13:30 Midday Range",
    subtitle: "Sideways Liquidity Protection",
    tag: "Theta Shield Active",
    color: "from-amber-500/20 to-yellow-500/10 border-amber-500/30 text-amber-400",
    strikeDelta: "Δ ≈ 0.50 ATM (Cooldown)",
    activeModels: "Exhaustion & 1M Scalps",
    riskStatus: "120-Min Max Hold Limit Enforced",
    aiBriefing: "Market volume contracted below 30-day median; false breakout suppression filter active.",
    expectedPoints: "+15 to +25 pts Scalp",
  },
  {
    id: "trend_ramp",
    title: "13:30–15:15 Afternoon Trend",
    subtitle: "Stepped TSL Profit Lock Ramp",
    tag: "Multi-Tier Ratchet",
    color: "from-emerald-500/20 to-teal-500/10 border-emerald-500/30 text-emerald-400",
    strikeDelta: "Δ ≈ 0.62 ITM (Trend Pulse)",
    activeModels: "5M Dynamic Trend & Heikin-Ashi",
    riskStatus: "+40 pt Gain → +20 pt Profit Locked",
    aiBriefing: "Heavy institutional buying across Nifty 50 constituents driving continuation into session highs.",
    expectedPoints: "+50 to +75 pts Trend",
  },
  {
    id: "expiry_dynamics",
    title: "Weekly Expiry Session",
    subtitle: "Tuesday (NIFTY) / Thursday (SENSEX)",
    tag: "Gamma Acceleration",
    color: "from-purple-500/20 to-pink-500/10 border-purple-500/30 text-purple-400",
    strikeDelta: "DTE < 0.25 (Delta Decay Compensated)",
    activeModels: "Dynamic Strike Offset Engine",
    riskStatus: "₹5,000 Hard Loss Breaker Primed",
    aiBriefing: "15:35 IST AI Post-Market Journal evaluates execution discipline and statutory slippage.",
    expectedPoints: "+30 to +60 pts Fast Alpha",
  }
];

// 6 Core Architectural Pillars for Deep-Dive Modals
const ARCH_PILLARS = [
  {
    title: "Delta-Optimized Strike Engine",
    badge: "Greeks Calculus",
    short: "Calculates Black-Scholes Greeks dynamically, targeting contracts with Delta ≈ 0.60–0.65 for rapid point velocity.",
    details: "Unlike basic ATM simulators, NUKEBOX evaluates real-time Black-Scholes Greeks (Delta, Gamma, Theta, Vega) across all active strikes. It systematically targets Delta ≈ 0.60 to ensure optimal point velocity while hedging against time-decay acceleration.",
    icon: Cpu,
    color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20"
  },
  {
    title: "Multi-Tier Stepped TSL",
    badge: "Profit Protection",
    short: "Automated ratchet stops: +20 pt locks break-even, +40 pt locks +20 pt, and +60 pt locks +40 pt profit without emotional drag.",
    details: "NUKEBOX replaces emotional discretionary trailing with a multi-stage deterministic ratchet. At +20 pts gain, Stop Loss is locked to entry (₹0 risk). At +40 pts gain, +20 pts is locked in. At +60 pts gain, +40 pts is guaranteed.",
    icon: ShieldCheck,
    color: "text-purple-400 bg-purple-500/10 border-purple-500/20"
  },
  {
    title: "Dual AI Market Intelligence",
    badge: "Autonomous Agents",
    short: "08:50 AM Pre-Market Catalyst briefing from global news + 15:35 IST automated post-market trade debrief and discipline scoring.",
    details: "Features two dedicated AI models: (1) 08:50 AM Pre-Market Catalyst Agent synthesizing GIFT Nifty, global cues, and institutional bias; (2) 15:35 IST Post-Market Trade Journal analyzing win-rates, execution discipline, and session performance grade.",
    icon: Bot,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
  },
  {
    title: "₹5,000 Hard Loss Circuit Breaker",
    badge: "Risk Killswitch",
    short: "Strict intraday capital protection halts trading automatically if total daily drawdown hits the ₹5,000 risk threshold.",
    details: "Capital preservation is paramount. If the cumulative realized or unrealized drawdown reaches ₹5,000 in a single trading session, the risk engine immediately halts all strategy signal generation for the day.",
    icon: Zap,
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20"
  },
  {
    title: "120-Minute Theta Decay Shield",
    badge: "Time Exit",
    short: "Eliminates midday sideways theta decay by automatically squaring off stagnant positions that exceed maximum intraday duration.",
    details: "Options are decaying assets. If an active position remains in a narrow consolidation band for 120 minutes without hitting target or stop loss, NUKEBOX initiates an automatic time exit to protect accumulated premium.",
    icon: Clock,
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20"
  },
  {
    title: "Signed Cumulative Volume Delta",
    badge: "Order Flow",
    short: "Tick-by-tick order flow analysis tracks institutional buyer vs seller aggression at key support and resistance levels.",
    details: "Integrates real-time tick volume delta to confirm whether large participants are aggressively lifting asks or hitting bids, filtering out deceptive low-volume wick breakouts.",
    icon: Activity,
    color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20"
  }
];

function fmtNum(v) {
  return v == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function LandingScreen({ onLoginClick }) {
  const [activeFilter, setActiveFilter] = useState("ALL");
  const [activeRegime, setActiveRegime] = useState(MARKET_REGIMES[0]);
  const [selectedPillar, setSelectedPillar] = useState(null);
  
  // Tax Calculator States
  const [entryPrice, setEntryPrice] = useState(200);
  const [exitPrice, setExitPrice] = useState(245);
  const [lotQty, setLotQty] = useState(65);
  const [marketData, setMarketData] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/public/market-summary`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setMarketData(d);
      })
      .catch(() => {});
  }, []);

  // Indian Regulatory Tax Schedule Math
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

  const filteredStrats = FLEET_21_STRATEGIES.filter((s) => {
    if (activeFilter === "NIFTY") return s.index.includes("NIFTY");
    if (activeFilter === "SENSEX") return s.index.includes("SENSEX");
    if (activeFilter === "5M") return s.tf === "5M";
    if (activeFilter === "1M") return s.tf === "1M";
    return true;
  });

  const heroBgUrl = `${import.meta.env.BASE_URL}assets/quant_hero_bg.jpg`;

  return (
    <div className="min-h-screen bg-surface2 text-primary selection:bg-accent selection:text-white font-sans overflow-x-hidden">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 border-b border-subtle/80 bg-surface/95 backdrop-blur-2xl px-4 sm:px-8 py-3.5 shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <NukeBoxLogo size="md" />

          <div className="flex items-center gap-3">
            <a
              href="mailto:parthisivaram45@gmail.com?subject=Access%20Request%20for%20NUKEBOX%20Quant%20Terminal"
              className="hidden sm:flex items-center gap-1.5 rounded-xl border border-subtle bg-surface2 px-4 py-2 text-xs font-bold text-muted hover:bg-surface3 hover:text-white transition shadow-sm"
            >
              <Mail className="h-3.5 w-3.5 text-accent" />
              <span>Request Access</span>
            </a>

            <button
              onClick={onLoginClick}
              className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-accent to-indigo-600 px-4 py-2 text-xs font-black text-white hover:brightness-110 shadow-lg shadow-accent/25 transition cursor-pointer"
            >
              <Lock className="h-3.5 w-3.5" />
              <span>Operator Sign In</span>
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section with Cinematic Workstation Backdrop */}
      <section className="relative overflow-hidden pt-16 pb-20 px-4 sm:px-8 border-b border-subtle/40">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-25 mix-blend-luminosity pointer-events-none"
          style={{ backgroundImage: `url('${heroBgUrl}')` }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-surface2/40 via-surface2/85 to-surface2 pointer-events-none" />

        <div className="mx-auto max-w-5xl text-center space-y-6 relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-1.5 text-xs font-bold text-accent shadow-sm backdrop-blur-md"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Autonomous Options Quantitative Derivatives &amp; Risk Platform</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-tight"
          >
            Precision Algorithmic Options <br />
            <span className="bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Engineered by PARTHIBAKANNAN S
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mx-auto max-w-2xl text-sm sm:text-base text-gray-300 leading-relaxed font-sans"
          >
            NUKEBOX is an institutional quantitative derivatives sandbox built for NSE NIFTY 50 and BSE SENSEX options. Featuring 21 autonomous execution models, dynamic Greeks Delta strike selection (Delta ≈ 0.60), multi-tier stepped profit locks, and dual AI market debriefs.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-wrap items-center justify-center gap-3 pt-2"
          >
            <button
              onClick={onLoginClick}
              className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-accent to-indigo-600 px-6 py-3.5 text-sm font-black text-white hover:brightness-110 shadow-xl shadow-accent/30 transition transform hover:-translate-y-0.5 cursor-pointer"
            >
              <span>Launch Operator Terminal</span>
              <ArrowRight className="h-4 w-4" />
            </button>
            <a
              href="#strategies"
              className="flex items-center gap-2 rounded-2xl border border-subtle bg-surface2/80 px-5 py-3.5 text-sm font-bold text-gray-300 hover:bg-surface3 hover:text-white backdrop-blur-sm transition cursor-pointer"
            >
              <Eye className="h-4 w-4 text-cyan-400" />
              <span>Explore 21 Strategy Models</span>
            </a>
          </motion.div>

          {/* Calibrated Live Ticker Strip */}
          <div className="pt-8 max-w-3xl mx-auto">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-2xl border border-subtle bg-surface/80 backdrop-blur-xl shadow-md">
              {/* NIFTY Ticker */}
              <div className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-surface2/60 border border-subtle">
                <div className="text-left">
                  <span className="text-[10px] font-bold uppercase text-cyan-400 tracking-wider font-mono">NSE NIFTY 50 (Lot 65)</span>
                  <div className="font-mono text-lg font-black text-white tabular-nums">
                    {fmtNum(marketData?.nifty_price || 24823.15)}
                  </div>
                </div>
                <span className="rounded-full bg-bull/15 px-2.5 py-1 text-[11px] font-bold text-bull border border-bull/30 font-mono">
                  +{fmtNum(marketData?.nifty_change || 142.50)} (+{Number(marketData?.nifty_change_pct || 0.58).toFixed(2)}%)
                </span>
              </div>

              {/* SENSEX Ticker */}
              <div className="flex items-center justify-between px-4 py-2.5 rounded-xl bg-surface2/60 border border-subtle">
                <div className="text-left">
                  <span className="text-[10px] font-bold uppercase text-purple-400 tracking-wider font-mono">BSE SENSEX (Lot 20)</span>
                  <div className="font-mono text-lg font-black text-white tabular-nums">
                    {fmtNum(marketData?.sensex_price || 81388.40)}
                  </div>
                </div>
                <span className="rounded-full bg-bull/15 px-2.5 py-1 text-[11px] font-bold text-bull border border-bull/30 font-mono">
                  +{fmtNum(marketData?.sensex_change || 450.20)} (+{Number(marketData?.sensex_change_pct || 0.56).toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Market Regime & AI Engine Sandbox */}
      <section className="py-16 px-4 sm:px-8 border-t border-subtle/60 bg-surface/40 relative">
        <div className="mx-auto max-w-6xl space-y-8">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-3.5 py-1 text-xs font-bold text-indigo-400 border border-indigo-500/20">
              <Sliders className="h-3.5 w-3.5" />
              <span>Interactive Execution Sandbox</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white tracking-tight">Adaptive Market Regimes Simulation</h2>
            <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto font-sans">
              Select an intraday market scenario below to observe how NUKEBOX dynamically adjusts strike selection, enforces risk guardrails, and deploys AI debriefs.
            </p>
          </div>

          {/* Scenario Selection Tabs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {MARKET_REGIMES.map((regime) => {
              const isSelected = activeRegime.id === regime.id;
              return (
                <button
                  key={regime.id}
                  onClick={() => setActiveRegime(regime)}
                  className={`p-4 rounded-2xl border text-left transition-all cursor-pointer ${
                    isSelected
                      ? "bg-surface border-accent shadow-lg shadow-accent/20 ring-1 ring-accent"
                      : "bg-surface2/60 border-subtle hover:bg-surface2 hover:border-border-strong"
                  }`}
                >
                  <span className="text-[10px] font-mono font-bold uppercase text-accent">{regime.tag}</span>
                  <div className="text-sm font-bold text-white mt-1">{regime.title}</div>
                  <div className="text-xs text-gray-400 mt-0.5 line-clamp-1">{regime.subtitle}</div>
                </button>
              );
            })}
          </div>

          {/* Active Regime Telemetry Display */}
          <motion.div
            key={activeRegime.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className={`rounded-3xl border bg-gradient-to-br ${activeRegime.color} p-6 sm:p-8 backdrop-blur-xl space-y-6 shadow-2xl`}
          >
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-subtle/80 pb-4">
              <div>
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-gray-400">Active Scenario</span>
                <h3 className="text-xl sm:text-2xl font-black text-white">{activeRegime.title}</h3>
                <p className="text-xs text-gray-300 mt-0.5">{activeRegime.subtitle}</p>
              </div>

              <div className="flex items-center gap-2 rounded-2xl bg-surface/90 px-4 py-2 border border-subtle shadow-sm">
                <Target className="h-4 w-4 text-emerald-400" />
                <div className="text-left">
                  <span className="text-[9px] uppercase font-bold text-faint block">Target Velocity</span>
                  <span className="text-xs font-mono font-black text-emerald-400">{activeRegime.expectedPoints}</span>
                </div>
              </div>
            </div>

            {/* 4 Telemetry Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1">
                <span className="text-[10px] uppercase font-bold text-faint flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-accent" /> Strike Selection Math
                </span>
                <div className="text-sm font-mono font-bold text-white">{activeRegime.strikeDelta}</div>
              </div>

              <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1">
                <span className="text-[10px] uppercase font-bold text-faint flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-purple-400" /> Active Strategy Models
                </span>
                <div className="text-sm font-mono font-bold text-white">{activeRegime.activeModels}</div>
              </div>

              <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1">
                <span className="text-[10px] uppercase font-bold text-faint flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Risk Guardrail Protocol
                </span>
                <div className="text-sm font-mono font-bold text-emerald-400">{activeRegime.riskStatus}</div>
              </div>
            </div>

            {/* AI Intelligence Stream */}
            <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1.5">
              <div className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-indigo-400" />
                <span className="text-xs font-bold text-white">NUKEBOX AI Intelligence Feed</span>
              </div>
              <p className="text-xs text-gray-300 font-sans leading-relaxed">
                "{activeRegime.aiBriefing}"
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* 6 Key Architectural Pillars with On-Demand Modal Triggers */}
      <section className="py-16 px-4 sm:px-8 max-w-7xl mx-auto space-y-6">
        <div className="text-center space-y-2 mb-10">
          <h2 className="text-2xl sm:text-3xl font-black text-white">Engineered for Quantitative Excellence</h2>
          <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
            Explore the institutional foundations powering NUKEBOX's high-speed execution sandbox. Click any card to inspect architecture.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {ARCH_PILLARS.map((p, idx) => {
            const Icon = p.icon;
            return (
              <div
                key={idx}
                onClick={() => setSelectedPillar(p)}
                className="rounded-3xl border border-subtle bg-surface/80 p-6 space-y-3 hover:border-accent/40 transition backdrop-blur-md cursor-pointer group shadow-sm hover:shadow-lg"
              >
                <div className="flex items-center justify-between">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-2xl border ${p.color}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-[10px] font-mono font-bold uppercase text-faint group-hover:text-accent transition">
                    Learn More →
                  </span>
                </div>
                <h3 className="text-base font-bold text-white group-hover:text-accent transition">{p.title}</h3>
                <p className="text-xs text-gray-400 leading-relaxed font-sans">{p.short}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* 21-Strategy Fleet Overview (All Models Displayed with Categories) */}
      <section id="strategies" className="py-16 px-4 sm:px-8 max-w-7xl mx-auto space-y-8">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3.5 py-1 text-xs font-bold text-accent border border-accent/20">
            <Layers className="h-3.5 w-3.5" />
            <span>Quantitative Model Fleet</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black text-white">21 Autonomous Quantitative Strategies</h2>
          <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
            Systematic, non-discretionary execution models engineered specifically for Indian equity index derivatives microstructure.
          </p>

          {/* Filter Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-4">
            {[
              { key: "ALL", label: "All 21 Strategies" },
              { key: "NIFTY", label: "NIFTY 50 (10)" },
              { key: "SENSEX", label: "BSE SENSEX (11)" },
              { key: "5M", label: "5M High-Conviction (12)" },
              { key: "1M", label: "1M Micro-Scalps (9)" }
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => setActiveFilter(f.key)}
                className={`rounded-xl px-4 py-2 text-xs font-bold transition border cursor-pointer ${
                  activeFilter === f.key
                    ? "bg-accent text-white border-accent shadow-md shadow-accent/25"
                    : "bg-surface2 text-gray-400 border-subtle hover:text-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Strategy Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredStrats.map((s) => {
            const isCE = s.dir.includes("CE");
            return (
              <div key={s.id} className="rounded-2xl border border-subtle bg-surface/80 p-5 space-y-3 hover:border-accent/40 transition shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black border ${
                      s.index.includes("NIFTY") ? "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" : "bg-purple-500/15 text-purple-400 border-purple-500/30"
                    }`}>
                      {s.index}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      isCE ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                    }`}>
                      {s.dir}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-faint">{s.tf} • {s.mode}</span>
                </div>
                <h3 className="text-sm font-bold text-white tracking-tight">{s.name}</h3>
                <p className="text-xs text-gray-400 leading-relaxed font-sans">{s.desc}</p>
                <div className="pt-2 border-t border-subtle/60 flex items-center justify-between text-[10px] font-mono text-faint">
                  <span>Target Velocity: <strong className="text-emerald-400">Δ ≈ {s.targetDelta}</strong></span>
                  <span>Risk: <strong className="text-rose-400">20% SL</strong></span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Interactive Indian Regulatory Tax & Charges Calculator */}
      <section className="py-16 px-4 sm:px-8 border-t border-subtle/60 bg-surface/40">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/20">
              <Calculator className="h-3.5 w-3.5" />
              <span>Real-Time Statutory Deduction Schedule</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white">Indian Regulatory Tax Calculator</h2>
            <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto">
              NUKEBOX models exact statutory charges in real-time so your paper P&amp;L reflects true take-home performance.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 rounded-3xl border border-subtle bg-surface/90 p-6 sm:p-8 backdrop-blur-xl shadow-xl">
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

            {/* Itemized Split */}
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

      {/* Pillar Deep-Dive Modal */}
      <AnimatePresence>
        {selectedPillar && (
          <div
            onClick={() => setSelectedPillar(null)}
            className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-lg rounded-3xl border border-subtle bg-surface p-6 sm:p-8 shadow-2xl space-y-4"
            >
              <button
                onClick={() => setSelectedPillar(null)}
                className="absolute top-5 right-5 rounded-full p-2 text-faint hover:bg-surface2 hover:text-primary transition"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="flex items-center gap-2.5">
                <div className={`flex h-10 w-10 items-center justify-center rounded-2xl border ${selectedPillar.color}`}>
                  <selectedPillar.icon className="h-5 w-5" />
                </div>
                <div>
                  <span className="text-[10px] font-mono uppercase font-bold text-accent">{selectedPillar.badge}</span>
                  <h3 className="text-lg font-black text-white">{selectedPillar.title}</h3>
                </div>
              </div>

              <p className="text-xs text-gray-300 leading-relaxed font-sans pt-2">
                {selectedPillar.details}
              </p>

              <div className="pt-4 border-t border-subtle flex justify-end">
                <button
                  onClick={() => setSelectedPillar(null)}
                  className="rounded-xl bg-surface2 px-4 py-2 text-xs font-bold text-white hover:bg-surface3 transition"
                >
                  Close Specification
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Footer & Master Owner Details */}
      <footer className="border-t border-subtle bg-surface py-12 px-4 sm:px-8 text-xs text-faint">
        <div className="mx-auto max-w-7xl space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <NukeBoxLogo size="sm" />
            <div className="flex items-center gap-4 font-medium">
              <a
                href="mailto:parthisivaram45@gmail.com?subject=Access%20Request%20for%20NUKEBOX%20Quant%20Terminal"
                className="font-bold text-accent hover:underline flex items-center gap-1"
              >
                <Mail className="h-3.5 w-3.5" />
                <span>Contact Master Quant (PARTHIBAKANNAN S)</span>
              </a>
              <span>•</span>
              <button onClick={onLoginClick} className="font-bold text-primary hover:underline cursor-pointer">
                Operator Sign In
              </button>
            </div>
          </div>

          <p className="text-[11px] leading-relaxed text-gray-400 font-sans">
            <strong>Regulatory &amp; Compliance Notice:</strong> NUKEBOX is a proprietary simulated quantitative paper-trading and derivatives research platform developed and owned by <strong>PARTHIBAKANNAN S</strong>. All orders, executions, and P&amp;L calculations are strictly modeled within a deterministic sandbox with zero real-capital routing. Designed for quantitative strategy validation, risk management modeling, and execution research under Indian regulatory parameters.
          </p>

          <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-subtle/50 text-[10px] font-mono">
            <span>© 2026 NUKEBOX by PARTHIBAKANNAN S. All Rights Reserved.</span>
            <span>Master Email: parthisivaram45@gmail.com • NSE NIFTY (Lot 65) • BSE SENSEX (Lot 20)</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
