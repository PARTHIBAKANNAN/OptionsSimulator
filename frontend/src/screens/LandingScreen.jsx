import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck, Zap, Activity, Cpu, Sparkles, TrendingUp,
  BarChart3, ChevronRight, Lock, Mail, ArrowRight,
  Layers, CheckCircle2, Award, DollarSign, Calculator, Eye,
  Bot, Clock, HelpCircle, ArrowUpRight, ArrowDownRight, Globe,
  Sliders, Play, X, ExternalLink, RefreshCw, Terminal, Target,
  Search, Copy, Check, Info, FileText
} from "lucide-react";
import { NukeBoxLogo } from "../components/NukeBoxLogo";
import { API_BASE } from "../lib/apiBase";

// 21 Proprietary Algorithmic Strategies (Strictly high-level qualitative descriptions with zero math/logic leaks)
const FLEET_21_STRATEGIES = [
  { id: "NIFTY_ORB_BULLISH_5M_ITM", name: "NIFTY Opening Range Momentum CE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Opening Breakout Alpha", desc: "Captures morning opening momentum following initial session price discovery with macro trend alignment." },
  { id: "NIFTY_ORB_BEARISH_5M_ITM", name: "NIFTY Opening Range Breakdown PE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Opening Breakdown Alpha", desc: "Executes directional downside breakdowns on expanding negative order flow velocity." },
  { id: "NIFTY_EMA_BOUNCE_5M_ITM", name: "NIFTY Dynamic Support Pullback CE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Trend Continuation", desc: "Enters high-probability trend continuation pullbacks testing institutional dynamic support levels." },
  { id: "NIFTY_EMA_REJECTION_5M_ITM", name: "NIFTY Dynamic Resistance Rejection PE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Trend Continuation", desc: "Capitalizes on overhead resistance rejections aligned with higher-timeframe bearish momentum." },
  { id: "NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM", name: "NIFTY Directional Trend Pulse CE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Smoothed Trend Riding", desc: "Smoothed noise-filtered trend-following model capturing multi-candle directional thrusts." },
  { id: "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", name: "NIFTY Directional Trend Pulse PE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Smoothed Trend Riding", desc: "Rides sustained downward momentum pulses with clean directional confirmation." },
  { id: "NIFTY_STOCHASTIC_BOUNCE_5M_ITM", name: "NIFTY Oversold Exhaustion Reversal CE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Mean-Reversion Sweep", desc: "Exploits short-term oversold exhaustion bounces within primary uptrend regimes." },
  { id: "NIFTY_STOCHASTIC_REJECTION_5M_ITM", name: "NIFTY Overbought Exhaustion Reversal PE", index: "NIFTY 50", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Mean-Reversion Sweep", desc: "Captures rapid mean-reversion rejections from extended overbought supply zones." },
  { id: "NIFTY_1M_SCALP_CE", name: "NIFTY High-Velocity Micro Scalp CE", index: "NIFTY 50", tf: "1M", mode: "High-Frequency ATM", dir: "CE", profile: "Sub-Minute Momentum", desc: "Sub-minute momentum scalping engine exploiting instantaneous tick liquidity bursts." },
  { id: "NIFTY_1M_SCALP_PE", name: "NIFTY High-Velocity Micro Scalp PE", index: "NIFTY 50", tf: "1M", mode: "High-Frequency ATM", dir: "PE", profile: "Sub-Minute Momentum", desc: "High-frequency downside scalps executed within strict risk and time constraints." },

  { id: "SENSEX_ORB_BULLISH_5M_ITM", name: "SENSEX Index Breakout Expansion CE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Opening Breakout Alpha", desc: "High-velocity breakout model calibrated for BSE SENSEX 100-point strike spacing." },
  { id: "SENSEX_ORB_BEARISH_5M_ITM", name: "SENSEX Index Breakdown Expansion PE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Opening Breakdown Alpha", desc: "Captures rapid morning panic breakdowns on 30-share heavyweight index components." },
  { id: "SENSEX_EMA_BOUNCE_5M_ITM", name: "SENSEX Structural Support Pullback CE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Trend Continuation", desc: "Systematic pullback entries at structural moving average confluence zones." },
  { id: "SENSEX_EMA_REJECTION_5M_ITM", name: "SENSEX Structural Resistance Rejection PE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Trend Continuation", desc: "Downside rejection execution testing downward-sloping institutional resistance." },
  { id: "SENSEX_HEIKIN_ASHI_BULLISH_5M_ITM", name: "SENSEX Smoothed Trend Flow CE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Smoothed Trend Riding", desc: "Filters erratic intraday wicks to lock onto institutional multi-bar trend runs." },
  { id: "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", name: "SENSEX Smoothed Trend Flow PE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Smoothed Trend Riding", desc: "Bearish trend extension model with automated stepped trailing profit locks." },
  { id: "SENSEX_STOCHASTIC_BOUNCE_5M_ITM", name: "SENSEX Liquidity Sweep Reversal CE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "CE", profile: "Mean-Reversion Sweep", desc: "Trades sharp liquidity sweep reversals from extreme oversold conditions." },
  { id: "SENSEX_STOCHASTIC_REJECTION_5M_ITM", name: "SENSEX Liquidity Sweep Rejection PE", index: "SENSEX", tf: "5M", mode: "High-Conviction ITM", dir: "PE", profile: "Mean-Reversion Sweep", desc: "Reversal model executing on false breakouts at session resistance." },
  { id: "SENSEX_1M_SCALP_CE", name: "SENSEX High-Frequency Micro Scalp CE", index: "SENSEX", tf: "1M", mode: "High-Frequency ATM", dir: "CE", profile: "Sub-Minute Momentum", desc: "Rapid ATM scalp capture on explosive 1-minute volume surges." },
  { id: "SENSEX_1M_SCALP_PE", name: "SENSEX High-Frequency Micro Scalp PE", index: "SENSEX", tf: "1M", mode: "High-Frequency ATM", dir: "PE", profile: "Sub-Minute Momentum", desc: "Fast-reacting ATM PE scalp with deterministic stop loss guardrails." },
  { id: "SENSEX_ATM_VOLATILITY_EXPANSION", name: "SENSEX Volatility Surge Model", index: "SENSEX", tf: "1M", mode: "High-Frequency ATM", dir: "CE / PE", profile: "Volatility Expansion", desc: "Captures sudden expansion in implied volatility around macroeconomic events." }
];

// Interactive Market Regimes Simulation Scenarios
const MARKET_REGIMES = [
  {
    id: "morning_surge",
    title: "09:15–10:00 Morning Surge",
    subtitle: "High Conviction Opening Momentum",
    tag: "Volatile Expansion",
    color: "from-cyan-500/20 to-blue-500/10 border-cyan-500/30 text-cyan-400",
    strikeDelta: "Dynamic Deep ITM Targeting",
    activeModels: "5M High-Conviction Opening Breakouts",
    riskStatus: "Initial Stop Loss Protection Active",
    aiBriefing: "08:50 AM Pre-Market Catalyst detected positive GIFT Nifty delta (+85 pts) with banking sector accumulation.",
    expectedPoints: "High-Velocity Directional Alpha",
  },
  {
    id: "midday_chop",
    title: "11:30–13:30 Midday Range",
    subtitle: "Sideways Liquidity Protection",
    tag: "Theta Shield Active",
    color: "from-amber-500/20 to-yellow-500/10 border-amber-500/30 text-amber-400",
    strikeDelta: "Dynamic ATM Micro-Scalping",
    activeModels: "Exhaustion Reversals & 1M Scalps",
    riskStatus: "120-Minute Holding Limit Enforced",
    aiBriefing: "Market volume contracted below 30-day median; false breakout suppression filter active.",
    expectedPoints: "Controlled Micro Scalps",
  },
  {
    id: "trend_ramp",
    title: "13:30–15:15 Afternoon Trend",
    subtitle: "Stepped Profit Ratchet Ramp",
    tag: "Multi-Tier Ratchet",
    color: "from-emerald-500/20 to-teal-500/10 border-emerald-500/30 text-emerald-400",
    strikeDelta: "Delta-Optimized Trend Tracking",
    activeModels: "5M Dynamic Trend & Smoothed Flow",
    riskStatus: "Multi-Tier Profit Lock Ratchet Active",
    aiBriefing: "Heavy institutional buying across Nifty 50 constituents driving continuation into session highs.",
    expectedPoints: "Extended Multi-Bar Trend Expansion",
  },
  {
    id: "expiry_dynamics",
    title: "Weekly Expiry Session",
    subtitle: "Tuesday (NIFTY) / Thursday (SENSEX)",
    tag: "Gamma Acceleration",
    color: "from-purple-500/20 to-pink-500/10 border-purple-500/30 text-purple-400",
    strikeDelta: "Expiry Time-Decay Calibration",
    activeModels: "Dynamic Strike Offset Engine",
    riskStatus: "Hard Loss Circuit Breaker Primed",
    aiBriefing: "15:35 IST AI Post-Market Journal evaluates execution discipline and statutory slippage.",
    expectedPoints: "Sub-Second Systematic Execution",
  }
];

// 6 Core Architectural Pillars for Deep-Dive Modals
const ARCH_PILLARS = [
  {
    title: "Delta-Optimized Strike Engine",
    badge: "Greeks Modeling",
    short: "Calculates Black-Scholes Greeks dynamically, targeting high-velocity contracts for rapid point acceleration.",
    details: "NUKEBOX evaluates real-time Black-Scholes Greeks (Delta, Gamma, Theta, Vega) across all active strikes. It systematically targets Delta-optimized contracts to ensure rapid point velocity while hedging against time-decay acceleration.",
    icon: Cpu,
    color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20"
  },
  {
    title: "Multi-Tier Stepped TSL",
    badge: "Profit Protection",
    short: "Automated ratchet stops locking in profit milestones without discretionary interference.",
    details: "NUKEBOX replaces emotional discretionary trailing with a multi-stage deterministic ratchet. As option points expand, the Stop Loss is systematically raised at progressive profit milestones to guarantee capital protection.",
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
    title: "Hard Loss Circuit Breaker",
    badge: "Capital Preservation",
    short: "Strict intraday capital protection halts trading automatically if total daily drawdown reaches the risk limit.",
    details: "Capital preservation is paramount. If the cumulative drawdown reaches the configured daily risk threshold in a single trading session, the risk engine immediately halts all strategy signal generation for the day.",
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
  const [searchQuery, setSearchQuery] = useState("");
  const [activeRegime, setActiveRegime] = useState(MARKET_REGIMES[0]);
  const [selectedPillar, setSelectedPillar] = useState(null);
  const [showAccessModal, setShowAccessModal] = useState(false);
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [activeAiTab, setActiveAiTab] = useState("premarket");

  // Tax Calculator States
  const [entryPrice, setEntryPrice] = useState(200);
  const [exitPrice, setExitPrice] = useState(245);
  const [lotQty, setLotQty] = useState(65);
  const [marketData, setMarketData] = useState(null);

  // Fetch and auto-refresh live market summary
  useEffect(() => {
    function loadMarketData() {
      fetch(`${API_BASE}/api/public/market-summary`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (d) setMarketData(d);
        })
        .catch(() => {});
    }

    loadMarketData();
    const timer = setInterval(loadMarketData, 8000);
    return () => clearInterval(timer);
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

  // Filter and Search Logic
  const filteredStrats = FLEET_21_STRATEGIES.filter((s) => {
    const matchesFilter =
      activeFilter === "ALL" ||
      (activeFilter === "NIFTY" && s.index.includes("NIFTY")) ||
      (activeFilter === "SENSEX" && s.index.includes("SENSEX")) ||
      (activeFilter === "5M" && s.tf === "5M") ||
      (activeFilter === "1M" && s.tf === "1M");

    const matchesSearch =
      !searchQuery.trim() ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.profile.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.desc.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  const handleCopyEmail = () => {
    navigator.clipboard.writeText("parthisivaram45@gmail.com");
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  const heroBgUrl = `${import.meta.env.BASE_URL}assets/quant_hero_bg.jpg`;

  return (
    <div className="min-h-screen bg-surface2 text-primary selection:bg-accent selection:text-white font-sans overflow-x-hidden">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 border-b border-subtle/80 bg-surface/95 backdrop-blur-2xl px-4 sm:px-8 py-3.5 shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <NukeBoxLogo size="md" />

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAccessModal(true)}
              className="hidden sm:flex items-center gap-1.5 rounded-xl border border-subtle bg-surface2 px-4 py-2 text-xs font-bold text-muted hover:bg-surface3 hover:text-white transition shadow-sm cursor-pointer"
            >
              <Mail className="h-3.5 w-3.5 text-accent" />
              <span>Request Access</span>
            </button>

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

      {/* Hero Section with Workstation Backdrop */}
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
            <span>Autonomous Quantitative Options Execution &amp; Risk Modeling Sandbox</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-tight"
          >
            Precision Algorithmic Options <br />
            <span className="bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Autonomous Quantitative Derivatives Engine
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mx-auto max-w-2xl text-sm sm:text-base text-gray-300 leading-relaxed font-sans"
          >
            NUKEBOX is an institutional quantitative derivatives sandbox built for NSE NIFTY 50 and BSE SENSEX options. Featuring 21 autonomous execution models, dynamic Greeks Delta strike selection, multi-tier stepped profit locks, and dual AI market debriefs.
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

          {/* Auto-Updating Live Ticker Strip */}
          <div className="pt-8 max-w-3xl mx-auto space-y-3">
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

            {/* Live System Heartbeat Pill */}
            <div className="inline-flex items-center justify-center gap-3 px-4 py-1.5 rounded-full border border-subtle bg-surface/90 text-[10px] font-mono text-faint backdrop-blur-md shadow-sm">
              <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                SYSTEM NOMINAL
              </span>
              <span>•</span>
              <span>100% DETERMINISTIC SANDBOX</span>
              <span>•</span>
              <span className="text-gray-400">SEBI CALENDAR: TUE (NIFTY) / THU (SENSEX)</span>
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
                  <span className="text-[9px] uppercase font-bold text-faint block">Performance Objective</span>
                  <span className="text-xs font-mono font-black text-emerald-400">{activeRegime.expectedPoints}</span>
                </div>
              </div>
            </div>

            {/* 3 Telemetry Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1">
                <span className="text-[10px] uppercase font-bold text-faint flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-accent" /> Strike Selection Engine
                </span>
                <div className="text-sm font-bold text-white">{activeRegime.strikeDelta}</div>
              </div>

              <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1">
                <span className="text-[10px] uppercase font-bold text-faint flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5 text-purple-400" /> Active Strategy Models
                </span>
                <div className="text-sm font-bold text-white">{activeRegime.activeModels}</div>
              </div>

              <div className="rounded-2xl bg-surface/90 border border-subtle p-4 space-y-1">
                <span className="text-[10px] uppercase font-bold text-faint flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Risk Guardrail Protocol
                </span>
                <div className="text-sm font-bold text-emerald-400">{activeRegime.riskStatus}</div>
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

      {/* Dual AI Intelligence Spotlight Section */}
      <section className="py-16 px-4 sm:px-8 border-t border-subtle/60 bg-surface2/30">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3.5 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/20">
              <Bot className="h-3.5 w-3.5" />
              <span>Automated Institutional Intelligence</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white">Dual AI Market Intelligence Engine</h2>
            <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto font-sans">
              Autonomous analytical agents running before market open and after market close to synthesize macro sentiment and audit execution discipline.
            </p>
          </div>

          <div className="rounded-3xl border border-subtle bg-surface/90 p-6 sm:p-8 backdrop-blur-xl shadow-xl space-y-6">
            {/* AI Engine Switcher */}
            <div className="flex items-center justify-center gap-3 border-b border-subtle pb-4">
              <button
                onClick={() => setActiveAiTab("premarket")}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer border ${
                  activeAiTab === "premarket"
                    ? "bg-accent text-white border-accent shadow-md shadow-accent/25"
                    : "bg-surface2 text-gray-400 border-subtle hover:text-white"
                }`}
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>08:50 AM Pre-Market Catalyst Agent</span>
              </button>
              <button
                onClick={() => setActiveAiTab("postmarket")}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer border ${
                  activeAiTab === "postmarket"
                    ? "bg-purple-600 text-white border-purple-500 shadow-md shadow-purple-600/25"
                    : "bg-surface2 text-gray-400 border-subtle hover:text-white"
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>15:35 IST Post-Market Trade Journal</span>
              </button>
            </div>

            {/* AI Content Preview */}
            <AnimatePresence mode="wait">
              {activeAiTab === "premarket" ? (
                <motion.div
                  key="premarket"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  className="space-y-4 font-sans text-xs"
                >
                  <div className="flex items-center justify-between p-3 rounded-2xl bg-surface2 border border-subtle">
                    <div>
                      <span className="text-[10px] font-mono font-bold uppercase text-accent">Catalyst Synthesis</span>
                      <div className="text-sm font-bold text-white mt-0.5">Macro Bias: Moderately Bullish Opening Bias</div>
                    </div>
                    <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-[10px] font-mono font-bold text-emerald-400 border border-emerald-500/30">
                      GIFT NIFTY: +85 pts
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-gray-300">
                    <div className="p-3.5 rounded-2xl bg-surface2/60 border border-subtle space-y-1">
                      <strong className="text-white block font-mono text-[11px]">Key Global Drivers:</strong>
                      <p className="text-gray-400">US tech earnings resilience and softening crude futures supporting Asian markets.</p>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-surface2/60 border border-subtle space-y-1">
                      <strong className="text-white block font-mono text-[11px]">Intraday Strategy Alignment:</strong>
                      <p className="text-gray-400">Prioritizing 5M Opening Breakout (CE) models above session pivot resistance.</p>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="postmarket"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  className="space-y-4 font-sans text-xs"
                >
                  <div className="flex items-center justify-between p-3 rounded-2xl bg-surface2 border border-subtle">
                    <div>
                      <span className="text-[10px] font-mono font-bold uppercase text-purple-400">Session Scorecard</span>
                      <div className="text-sm font-bold text-white mt-0.5">Execution Grade: A- • Discipline Score: 94/100</div>
                    </div>
                    <span className="rounded-full bg-purple-500/15 px-2.5 py-1 text-[10px] font-mono font-bold text-purple-400 border border-purple-500/30">
                      RISK AUDIT: CLEAN
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-gray-300">
                    <div className="p-3.5 rounded-2xl bg-surface2/60 border border-subtle space-y-1">
                      <strong className="text-white block font-mono text-[11px]">Execution Strengths:</strong>
                      <p className="text-gray-400">Stepped TSL locked in profit steps seamlessly without emotional early manual exits.</p>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-surface2/60 border border-subtle space-y-1">
                      <strong className="text-white block font-mono text-[11px]">Areas for Review:</strong>
                      <p className="text-gray-400">120-minute holding limit cleanly eliminated theta decay during midday sideways chop.</p>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
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

      {/* 21-Strategy Fleet Overview (With Search Bar & Category Filters) */}
      <section id="strategies" className="py-16 px-4 sm:px-8 max-w-7xl mx-auto space-y-8">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3.5 py-1 text-xs font-bold text-accent border border-accent/20">
            <Layers className="h-3.5 w-3.5" />
            <span>Quantitative Model Fleet</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black text-white">21 Autonomous Quantitative Strategies</h2>
          <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto font-sans">
            Systematic, non-discretionary execution models engineered specifically for Indian equity index derivatives microstructure.
          </p>

          {/* Search Bar & Instant Filter Controls */}
          <div className="max-w-xl mx-auto pt-2 space-y-3">
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-faint" />
              <input
                type="text"
                placeholder="Search strategies by keyword (e.g., Breakout, Scalp, Reversal)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-2xl border border-subtle bg-surface px-10 py-2.5 text-xs text-primary placeholder:text-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent shadow-sm font-sans"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-faint hover:text-primary text-xs"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Category Filter Chips */}
            <div className="flex flex-wrap items-center justify-center gap-2">
              {[
                { key: "ALL", label: "All 21 Models" },
                { key: "NIFTY", label: "NIFTY 50 (10)" },
                { key: "SENSEX", label: "BSE SENSEX (11)" },
                { key: "5M", label: "5M High-Conviction (12)" },
                { key: "1M", label: "1M Micro-Scalps (9)" }
              ].map((f) => (
                <button
                  key={f.key}
                  onClick={() => setActiveFilter(f.key)}
                  className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition border cursor-pointer ${
                    activeFilter === f.key
                      ? "bg-accent text-white border-accent shadow-md shadow-accent/25"
                      : "bg-surface2 text-gray-400 border-subtle hover:text-white"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Results Counter */}
            <div className="text-[11px] font-mono text-faint">
              Showing <strong className="text-accent">{filteredStrats.length}</strong> of 21 Strategy Models
            </div>
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
                  <span>Profile: <strong className="text-cyan-400">{s.profile}</strong></span>
                  <span>Execution: <strong className="text-emerald-400">Automated</strong></span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Interactive Indian Regulatory Tax & Charges Calculator (With 1-Click Presets) */}
      <section className="py-16 px-4 sm:px-8 border-t border-subtle/60 bg-surface/40">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/20">
              <Calculator className="h-3.5 w-3.5" />
              <span>Real-Time Statutory Deduction Schedule</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white">Indian Regulatory Tax Calculator</h2>
            <p className="text-xs sm:text-sm text-gray-400 max-w-xl mx-auto font-sans">
              NUKEBOX models exact statutory charges in real-time so your paper P&amp;L reflects true take-home performance.
            </p>

            {/* 1-Click Quick Action Presets */}
            <div className="flex flex-wrap items-center justify-center gap-2 pt-3">
              <span className="text-[11px] font-mono text-faint mr-1">Quick Presets:</span>
              <button
                onClick={() => { setLotQty(65); setEntryPrice(200); setExitPrice(240); }}
                className="px-3 py-1 rounded-xl bg-surface2 border border-subtle text-[11px] font-bold text-gray-300 hover:bg-surface3 hover:text-white transition cursor-pointer"
              >
                NIFTY 1 Lot (+40 pt Target)
              </button>
              <button
                onClick={() => { setLotQty(130); setEntryPrice(200); setExitPrice(220); }}
                className="px-3 py-1 rounded-xl bg-surface2 border border-subtle text-[11px] font-bold text-gray-300 hover:bg-surface3 hover:text-white transition cursor-pointer"
              >
                NIFTY 2 Lots (+20 pt Scalp)
              </button>
              <button
                onClick={() => { setLotQty(20); setEntryPrice(300); setExitPrice(360); }}
                className="px-3 py-1 rounded-xl bg-surface2 border border-subtle text-[11px] font-bold text-gray-300 hover:bg-surface3 hover:text-white transition cursor-pointer"
              >
                SENSEX 1 Lot (+60 pt Trend)
              </button>
            </div>
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

      {/* Pillar Deep-Dive Specification Modal */}
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
                className="absolute top-5 right-5 rounded-full p-2 text-faint hover:bg-surface2 hover:text-primary transition cursor-pointer"
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
                  className="rounded-xl bg-surface2 px-4 py-2 text-xs font-bold text-white hover:bg-surface3 transition cursor-pointer"
                >
                  Close Specification
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* In-Page Request Access Glassmorphic Modal */}
      <AnimatePresence>
        {showAccessModal && (
          <div
            onClick={() => setShowAccessModal(false)}
            className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-md rounded-3xl border border-subtle bg-surface p-6 sm:p-8 shadow-2xl space-y-5"
            >
              <button
                onClick={() => setShowAccessModal(false)}
                className="absolute top-5 right-5 rounded-full p-2 text-faint hover:bg-surface2 hover:text-primary transition cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="space-y-2">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent/15 text-accent border border-accent/30">
                  <Mail className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-black text-white">Request Terminal Access</h3>
                <p className="text-xs text-gray-400 font-sans">
                  Account provisioning is managed directly by the platform owner. Send an access request email to receive operator credentials.
                </p>
              </div>

              <div className="p-3.5 rounded-2xl bg-surface2 border border-subtle space-y-2 font-mono text-xs">
                <div className="flex justify-between items-center text-gray-300">
                  <span className="text-[10px] font-bold text-faint font-sans uppercase">Master Owner:</span>
                  <span className="text-white font-bold">PARTHIBAKANNAN S</span>
                </div>
                <div className="flex justify-between items-center text-gray-300">
                  <span className="text-[10px] font-bold text-faint font-sans uppercase">Direct Email:</span>
                  <span className="text-accent font-bold">parthisivaram45@gmail.com</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <a
                  href="mailto:parthisivaram45@gmail.com?subject=Access%20Request%20for%20NUKEBOX%20Quant%20Terminal"
                  className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-indigo-600 px-4 py-2.5 text-xs font-black text-white hover:brightness-110 shadow-md transition"
                >
                  <Mail className="h-4 w-4" />
                  <span>Send Email Request</span>
                </a>
                <button
                  onClick={handleCopyEmail}
                  className="flex items-center gap-1.5 rounded-xl border border-subtle bg-surface2 px-3.5 py-2.5 text-xs font-bold text-gray-300 hover:bg-surface3 hover:text-white transition cursor-pointer"
                >
                  {copiedEmail ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                  <span>{copiedEmail ? "Copied!" : "Copy"}</span>
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
              <button
                onClick={() => setShowAccessModal(true)}
                className="font-bold text-accent hover:underline flex items-center gap-1 cursor-pointer"
              >
                <Mail className="h-3.5 w-3.5" />
                <span>Contact Master Quant (PARTHIBAKANNAN S)</span>
              </button>
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
