import { useState, useEffect } from "react";
import { 
  ShieldAlert, 
  RotateCcw, 
  AlertTriangle, 
  CheckCircle2, 
  Wifi, 
  Sliders, 
  Activity, 
  Clock,
  Layers,
  TrendingUp,
  AlertCircle,
  RefreshCw,
  ShieldCheck,
  Server,
  Zap,
  Volume2,
  VolumeX,
  Palette,
  Bell,
  Database,
  Lock,
  Download,
  Trash2,
  Send,
  Eye,
  Check
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { API_BASE } from "../lib/apiBase";
import { soundEngine } from "../utils/audioAlerts";
import { 
  PALETTE_PRESETS, 
  DEFAULT_PALETTE_ID, 
  getActivePalette, 
  savePresetPalette, 
  saveCustomPalette 
} from "../utils/chartPalette";

export function SettingsScreen({ onOpenAliceLogin }) {
  // Navigation active sub-tab
  const [activeTab, setActiveTab] = useState("appearance");

  // Telemetry & WebSocket state
  const [telemetry, setTelemetry] = useState(null);
  const [telemetryLoading, setTelemetryLoading] = useState(true);
  const [telemetryError, setTelemetryError] = useState(null);
  const [wsPingMs, setWsPingMs] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Settings & Emergency operations state
  const [closingAll, setClosingAll] = useState(false);
  const [restartingAll, setRestartingAll] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);

  // Sound Engine state
  const [soundMuted, setSoundMuted] = useState(soundEngine.isMuted());
  const [soundVolume, setSoundVolume] = useState(Math.round(soundEngine.getVolume() * 100));

  // Chart Palette & Custom Color state
  const [currentPalette, setCurrentPalette] = useState(getActivePalette());
  const [customColors, setCustomColors] = useState({
    upColor: currentPalette.upColor,
    downColor: currentPalette.downColor,
    vwapColor: currentPalette.vwapColor,
    ema20Color: currentPalette.ema20Color,
    ema50Color: currentPalette.ema50Color,
    volumeUp: currentPalette.volumeUp,
    volumeDown: currentPalette.volumeDown,
  });

  // Execution & Strategy Controls (Preserving 100% Unrestricted Production Defaults)
  const [directionBias, setDirectionBias] = useState(() => {
    return localStorage.getItem("nukebox_direction_bias") || "BOTH";
  });
  const [tier1m, setTier1m] = useState(() => {
    return localStorage.getItem("nukebox_tier_1m") !== "false";
  });
  const [tier5m, setTier5m] = useState(() => {
    return localStorage.getItem("nukebox_tier_5m") !== "false";
  });
  const [tierExpansion, setTierExpansion] = useState(() => {
    return localStorage.getItem("nukebox_tier_expansion") !== "false";
  });

  // Risk Circuit Breakers (Disabled by default as requested)
  const [lossLimitActive, setLossLimitActive] = useState(() => {
    return localStorage.getItem("nukebox_loss_limit_active") === "true";
  });
  const [lossLimitAmount, setLossLimitAmount] = useState(() => {
    return localStorage.getItem("nukebox_loss_limit_amount") || "15000";
  });
  const [profitLockActive, setProfitLockActive] = useState(() => {
    return localStorage.getItem("nukebox_profit_lock_active") === "true";
  });
  const [profitLockAmount, setProfitLockAmount] = useState(() => {
    return localStorage.getItem("nukebox_profit_lock_amount") || "30000";
  });
  const [statutoryCharges, setStatutoryCharges] = useState(() => {
    return localStorage.getItem("nukebox_statutory_charges") !== "false";
  });

  // Chart Preferences
  const [defaultTimeframe, setDefaultTimeframe] = useState(() => {
    return localStorage.getItem("nukebox_default_timeframe") || "5m";
  });
  const [showGridlines, setShowGridlines] = useState(() => {
    return localStorage.getItem("nukebox_show_gridlines") !== "false";
  });

  const handleToggleSound = () => {
    const next = soundEngine.toggleMute();
    setSoundMuted(next);
    if (!next) {
      soundEngine.playOrderEntry();
    }
  };

  const handleVolumeChange = (e) => {
    const val = parseInt(e.target.value, 10);
    setSoundVolume(val);
    soundEngine.setVolume(val / 100);
  };

  const handleSelectPreset = (presetId) => {
    savePresetPalette(presetId);
    const updated = getActivePalette();
    setCurrentPalette(updated);
    setCustomColors({
      upColor: updated.upColor,
      downColor: updated.downColor,
      vwapColor: updated.vwapColor,
      ema20Color: updated.ema20Color,
      ema50Color: updated.ema50Color,
      volumeUp: updated.volumeUp,
      volumeDown: updated.volumeDown,
    });
    setActionMessage({
      type: "success",
      text: `Applied "${updated.name}" chart color palette.`
    });
  };

  const handleSaveCustomColors = () => {
    saveCustomPalette(customColors);
    setCurrentPalette(getActivePalette());
    setActionMessage({
      type: "success",
      text: "Custom layer palette saved and applied to all charts."
    });
  };

  const handleResetColors = () => {
    handleSelectPreset(DEFAULT_PALETTE_ID);
  };

  // Measure HTTP API Round-Trip Time & fetch live telemetry
  const fetchTelemetry = async () => {
    const t0 = performance.now();
    try {
      const res = await fetch(`${API_BASE}/api/public/telemetry`);
      const data = await res.json();
      const t1 = performance.now();
      setWsPingMs(Math.round(t1 - t0));
      setTelemetry(data);
      setTelemetryError(null);
    } catch (err) {
      setTelemetryError(err.message);
    } finally {
      setTelemetryLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTelemetry, 2000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const latency = telemetry?.latency_telemetry;
  const corridor = telemetry?.corridor;
  const spot = telemetry?.spot || {};

  async function handleSquareOffAll() {
    setClosingAll(true);
    try {
      const res = await fetch("/api/paper/positions/close-all", { method: "POST" });
      const data = await res.json();
      soundEngine.playSquareOff();
      setActionMessage({
        type: "success",
        text: `Successfully squared off ${data.closed_count || 0} open positions across all strategies.`
      });
      setShowConfirmModal(false);
    } catch (e) {
      setActionMessage({
        type: "error",
        text: `Square Off All failed: ${e.message}`
      });
    } finally {
      setClosingAll(false);
    }
  }

  async function handleRestartAll() {
    setRestartingAll(true);
    try {
      const res = await fetch("/api/paper/strategies/restart-all", { method: "POST" });
      const data = await res.json();
      soundEngine.playOrderEntry();
      setActionMessage({
        type: "success",
        text: `Re-armed and restarted all ${data.restarted_count || 44} strategies for the session.`
      });
    } catch (e) {
      setActionMessage({
        type: "error",
        text: `Restart failed: ${e.message}`
      });
    } finally {
      setRestartingAll(false);
    }
  }

  // Sub-Navigation Tabs Definitions
  const navTabs = [
    { id: "appearance", label: "Appearance & Charts", shortLabel: "Charts", icon: Palette },
    { id: "execution", label: "Execution & Strategies", shortLabel: "Exec", icon: Zap },
    { id: "risk", label: "Risk & Circuit Breakers", shortLabel: "Risk", icon: ShieldAlert },
    { id: "broker", label: "Broker & Live Stream", shortLabel: "Broker", icon: Server },
    { id: "sound", label: "Sound & Audio Alerts", shortLabel: "Audio", icon: Volume2 },
    { id: "data", label: "Data & Maintenance", shortLabel: "Data", icon: Database },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-16">
      {/* 1. Header Bar with System Status & Auto-refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shrink-0">
            <Sliders className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-primary flex items-center gap-2">
              Settings &amp; Quant Control Center
            </h1>
            <p className="text-xs text-faint mt-0.5">
              Multi-tab workspace configuration, institutional charting styles, live execution gates, and risk parameters.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-bold transition border ${
              autoRefresh 
                ? "bg-accent/15 text-accent border-accent/40 shadow-sm" 
                : "bg-surface2 text-faint border-subtle hover:text-primary"
            }`}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${autoRefresh ? "animate-spin" : ""}`} />
            <span>{autoRefresh ? "Auto-refresh: 2s" : "Paused"}</span>
          </button>
        </div>
      </div>

      {/* Action Notification Banner */}
      <AnimatePresence>
        {actionMessage && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className={`flex items-center justify-between rounded-xl border p-4 text-xs font-semibold ${
              actionMessage.type === "success"
                ? "bg-bull/10 border-bull/30 text-bull"
                : "bg-bear/10 border-bear/30 text-bear"
            }`}
          >
            <div className="flex items-center gap-2">
              {actionMessage.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              )}
              <span>{actionMessage.text}</span>
            </div>
            <button
              onClick={() => setActionMessage(null)}
              className="ml-4 font-bold opacity-70 hover:opacity-100"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 2. Main Two-Column Layout: Left-Side Navigation Dock + Main Stage */}
      <div className="flex flex-row gap-2 sm:gap-4 md:gap-6 min-h-[640px]">
        {/* LEFT-SIDE SUB-NAVIGATION BUTTONS (Desktop full width, Mobile compact icon dock with micro-labels) */}
        <aside className="w-16 sm:w-20 md:w-64 shrink-0 flex flex-col gap-1 sm:gap-1.5 rounded-2xl md:rounded-3xl border border-subtle bg-surface p-1.5 sm:p-2 md:p-3 shadow-md self-start sticky top-20">
          <div className="px-2 py-1.5 hidden md:block text-[10px] font-bold uppercase tracking-wider text-faint border-b border-subtle mb-1">
            Navigation
          </div>

          {navTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex flex-col md:flex-row items-center justify-center md:justify-start gap-1 md:gap-3 w-full rounded-xl md:rounded-2xl py-2 px-1 md:py-2.5 md:px-3 text-xs font-bold transition relative group ${
                  isActive
                    ? "bg-accent/15 text-accent border border-accent/40 shadow-sm"
                    : "text-faint hover:text-primary hover:bg-surface2/60 border border-transparent"
                }`}
                title={tab.label}
              >
                {isActive && (
                  <span className="hidden md:block absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-accent rounded-r-full" />
                )}
                <Icon className={`h-4 w-4 shrink-0 transition-transform group-active:scale-90 ${isActive ? "text-accent" : "text-faint"}`} />
                <span className="text-[9px] sm:text-[10px] font-bold tracking-tight text-center leading-none md:hidden truncate w-full">
                  {tab.shortLabel}
                </span>
                <span className="hidden md:inline font-sans truncate">{tab.label}</span>
              </button>
            );
          })}
        </aside>

        {/* RIGHT MAIN STAGE CONTENT */}
        <main className="flex-1 min-w-0 space-y-6">
          {/* TAB 1: 🎨 APPEARANCE & CHARTS */}
          {activeTab === "appearance" && (
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
              {/* Preset Palettes */}
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold text-primary flex items-center gap-2">
                      <Palette className="h-4 w-4 text-accent" />
                      <span>Curated Chart Color Palettes</span>
                    </h2>
                    <p className="text-xs text-faint mt-0.5">
                      Select an institutional preset or fine-tune custom colors for individual indicators and candles below.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {Object.values(PALETTE_PRESETS).map((p) => {
                    const isSelected = !currentPalette.isCustom && currentPalette.id === p.id;
                    return (
                      <div
                        key={p.id}
                        onClick={() => handleSelectPreset(p.id)}
                        className={`cursor-pointer rounded-2xl border p-4 transition flex flex-col justify-between ${
                          isSelected
                            ? "bg-accent/10 border-accent/50 shadow-md ring-1 ring-accent"
                            : "bg-surface2/50 border-subtle hover:border-accent/40 hover:bg-surface2"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <span className="font-bold text-xs text-primary">{p.name}</span>
                          {isSelected && <Check className="h-4 w-4 text-accent" />}
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="h-5 w-5 rounded-full border border-subtle" style={{ backgroundColor: p.upColor }} title="Bull Candle" />
                          <span className="h-5 w-5 rounded-full border border-subtle" style={{ backgroundColor: p.downColor }} title="Bear Candle" />
                          <span className="h-5 w-5 rounded-full border border-subtle" style={{ backgroundColor: p.vwapColor }} title="VWAP Line" />
                          <span className="h-5 w-5 rounded-full border border-subtle" style={{ backgroundColor: p.ema20Color }} title="EMA 20" />
                          <span className="h-5 w-5 rounded-full border border-subtle" style={{ backgroundColor: p.ema50Color }} title="EMA 50" />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Granular Layer Color Studio */}
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-primary">Granular Custom Layer Studio</h3>
                    <p className="text-xs text-faint mt-0.5">
                      Customize hex codes for each layer independently. Live changes apply across all charts.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleResetColors}
                      className="rounded-xl border border-subtle bg-surface2 px-3 py-1.5 text-xs font-bold text-faint hover:text-primary transition"
                    >
                      Reset to Preset
                    </button>
                    <button
                      onClick={handleSaveCustomColors}
                      className="rounded-xl bg-accent hover:bg-accent/90 text-white px-4 py-1.5 text-xs font-bold transition shadow-sm"
                    >
                      Save Custom Theme
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 text-xs font-mono">
                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">Bullish Candle</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.upColor}
                        onChange={(e) => setCustomColors({ ...customColors, upColor: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.upColor}</span>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">Bearish Candle</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.downColor}
                        onChange={(e) => setCustomColors({ ...customColors, downColor: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.downColor}</span>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">VWAP Line</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.vwapColor}
                        onChange={(e) => setCustomColors({ ...customColors, vwapColor: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.vwapColor}</span>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">EMA 20 Line</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.ema20Color}
                        onChange={(e) => setCustomColors({ ...customColors, ema20Color: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.ema20Color}</span>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">EMA 50 Line</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.ema50Color}
                        onChange={(e) => setCustomColors({ ...customColors, ema50Color: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.ema50Color}</span>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">Volume Up</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.volumeUp}
                        onChange={(e) => setCustomColors({ ...customColors, volumeUp: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.volumeUp}</span>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-3 space-y-2">
                    <span className="text-faint text-[10px] uppercase font-bold">Volume Down</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={customColors.volumeDown}
                        onChange={(e) => setCustomColors({ ...customColors, volumeDown: e.target.value })}
                        className="h-8 w-8 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="font-bold text-primary">{customColors.volumeDown}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Chart Display Preferences */}
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-primary">Chart Display &amp; Scaling Preferences</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-4 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-primary">Default Startup Timeframe</span>
                      <p className="text-faint text-[11px] mt-0.5">Timeframe selected when launching chart modal</p>
                    </div>
                    <select
                      value={defaultTimeframe}
                      onChange={(e) => {
                        setDefaultTimeframe(e.target.value);
                        localStorage.setItem("nukebox_default_timeframe", e.target.value);
                      }}
                      className="rounded-xl border border-subtle bg-surface px-3 py-1.5 font-bold text-primary font-mono"
                    >
                      <option value="1m">1m</option>
                      <option value="3m">3m</option>
                      <option value="5m">5m (Recommended)</option>
                      <option value="15m">15m</option>
                    </select>
                  </div>

                  <div className="rounded-2xl border border-subtle bg-surface2/40 p-4 flex items-center justify-between">
                    <div>
                      <span className="font-bold text-primary">Show Price Gridlines</span>
                      <p className="text-faint text-[11px] mt-0.5">Horizontal price guide markers on canvas</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={showGridlines}
                      onChange={(e) => {
                        setShowGridlines(e.target.checked);
                        localStorage.setItem("nukebox_show_gridlines", e.target.checked.toString());
                      }}
                      className="h-5 w-5 rounded accent-accent cursor-pointer"
                    />
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 2: ⚡ EXECUTION & STRATEGIES */}
          {activeTab === "execution" && (
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
              {/* Emergency Operations */}
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-4">
                <h2 className="text-sm font-bold text-primary flex items-center gap-2">
                  <Zap className="h-4 w-4 text-accent" />
                  <span>Master Emergency Execution Operations</span>
                </h2>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl border border-bear/30 bg-bear/5 p-5 space-y-3">
                    <h3 className="font-bold text-sm text-primary">Emergency Square Off All</h3>
                    <p className="text-xs text-faint leading-relaxed">
                      Immediately market-closes all active positions across all 44 systematic strategies.
                    </p>
                    <button
                      onClick={() => setShowConfirmModal(true)}
                      disabled={closingAll}
                      className="w-full rounded-xl bg-bear hover:bg-bear/90 text-white py-2.5 text-xs font-bold transition shadow-md shadow-bear/20 flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50"
                    >
                      <AlertTriangle className="h-4 w-4" />
                      <span>{closingAll ? "Closing All Positions…" : "Square Off All Positions"}</span>
                    </button>
                  </div>

                  <div className="rounded-2xl border border-accent/30 bg-accent/5 p-5 space-y-3">
                    <h3 className="font-bold text-sm text-primary">Restart &amp; Re-Arm Strategies</h3>
                    <p className="text-xs text-faint leading-relaxed">
                      Clears signal latches, resets cooldown timestamps, and re-evaluates fresh entries.
                    </p>
                    <button
                      onClick={handleRestartAll}
                      disabled={restartingAll}
                      className="w-full rounded-xl bg-accent hover:bg-accent/90 text-white py-2.5 text-xs font-bold transition shadow-md shadow-accent/25 flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50"
                    >
                      <RotateCcw className={`h-4 w-4 ${restartingAll ? "animate-spin" : ""}`} />
                      <span>{restartingAll ? "Re-Arming All Strategies…" : "Restart & Re-Arm All 44"}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Strategy Tier Controls */}
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-primary">Strategy Roster Tiers &amp; Execution Filters</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3.5 rounded-2xl bg-surface2/40 border border-subtle">
                    <div>
                      <span className="font-bold text-xs text-primary">1M Momentum Scalp Tier (14 Strategies)</span>
                      <p className="text-faint text-[11px] mt-0.5">High-velocity multi-timeframe scalps anchored to 5M trends</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={tier1m}
                      onChange={(e) => {
                        setTier1m(e.target.checked);
                        localStorage.setItem("nukebox_tier_1m", e.target.checked.toString());
                      }}
                      className="h-5 w-5 rounded accent-accent cursor-pointer"
                    />
                  </div>

                  <div className="flex items-center justify-between p-3.5 rounded-2xl bg-surface2/40 border border-subtle">
                    <div>
                      <span className="font-bold text-xs text-primary">5M Institutional Trend Tier (18 Strategies)</span>
                      <p className="text-faint text-[11px] mt-0.5">Core VWAP, Heikin-Ashi, and Supertrend ITM strategies</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={tier5m}
                      onChange={(e) => {
                        setTier5m(e.target.checked);
                        localStorage.setItem("nukebox_tier_5m", e.target.checked.toString());
                      }}
                      className="h-5 w-5 rounded accent-accent cursor-pointer"
                    />
                  </div>

                  <div className="flex items-center justify-between p-3.5 rounded-2xl bg-surface2/40 border border-subtle">
                    <div>
                      <span className="font-bold text-xs text-primary">Volatility Expansion Tier (12 Strategies)</span>
                      <p className="text-faint text-[11px] mt-0.5">Bollinger Band breakout, CMF flow, and Day-High/Low expansion</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={tierExpansion}
                      onChange={(e) => {
                        setTierExpansion(e.target.checked);
                        localStorage.setItem("nukebox_tier_expansion", e.target.checked.toString());
                      }}
                      className="h-5 w-5 rounded accent-accent cursor-pointer"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="p-4 rounded-2xl bg-surface2/40 border border-subtle space-y-2">
                    <span className="font-bold text-xs text-primary">Directional Bias Filter</span>
                    <p className="text-faint text-[11px]">Control whether Call (CE) or Put (PE) trades are allowed</p>
                    <div className="flex items-center gap-2 pt-1">
                      {["BOTH", "CE_ONLY", "PE_ONLY"].map((mode) => (
                        <button
                          key={mode}
                          onClick={() => {
                            setDirectionBias(mode);
                            localStorage.setItem("nukebox_direction_bias", mode);
                          }}
                          className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition border ${
                            directionBias === mode
                              ? "bg-accent/15 text-accent border-accent/40 shadow-sm"
                              : "bg-surface text-faint border-subtle hover:text-primary"
                          }`}
                        >
                          {mode.replace("_", " ")}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 3: 🛡️ RISK & CIRCUIT BREAKERS */}
          {activeTab === "risk" && (
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-5">
                <div>
                  <h2 className="text-sm font-bold text-primary flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-accent" />
                    <span>Quantitative Risk Management &amp; Circuit Breakers</span>
                  </h2>
                  <p className="text-xs text-faint mt-0.5">
                    Defensive safety limits and execution cost assumptions. Disabled by default to preserve unconstrained testing.
                  </p>
                </div>

                <div className="space-y-4">
                  {/* Daily Drawdown Circuit Breaker */}
                  <div className="p-4 rounded-2xl bg-surface2/40 border border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-primary">Daily Drawdown Circuit Breaker</span>
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
                          lossLimitActive ? "bg-bear/15 text-bear" : "bg-surface text-faint"
                        }`}>
                          {lossLimitActive ? "ACTIVE" : "DISABLED"}
                        </span>
                      </div>
                      <p className="text-faint text-[11px] mt-0.5">
                        Liquidates open positions and halts all entries if cumulative intraday loss reaches limit.
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1 font-mono text-xs">
                        <span className="text-faint font-bold">₹</span>
                        <input
                          type="number"
                          step="1000"
                          value={lossLimitAmount}
                          disabled={!lossLimitActive}
                          onChange={(e) => {
                            setLossLimitAmount(e.target.value);
                            localStorage.setItem("nukebox_loss_limit_amount", e.target.value);
                          }}
                          className="w-24 rounded-xl border border-subtle bg-surface px-2.5 py-1 font-bold text-primary disabled:opacity-50"
                        />
                      </div>
                      <input
                        type="checkbox"
                        checked={lossLimitActive}
                        onChange={(e) => {
                          setLossLimitActive(e.target.checked);
                          localStorage.setItem("nukebox_loss_limit_active", e.target.checked.toString());
                        }}
                        className="h-5 w-5 rounded accent-accent cursor-pointer"
                      />
                    </div>
                  </div>

                  {/* Daily Profit Lock */}
                  <div className="p-4 rounded-2xl bg-surface2/40 border border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-primary">Daily Profit Lock (Trailing Protection)</span>
                        <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
                          profitLockActive ? "bg-bull/15 text-bull" : "bg-surface text-faint"
                        }`}>
                          {profitLockActive ? "ACTIVE" : "DISABLED"}
                        </span>
                      </div>
                      <p className="text-faint text-[11px] mt-0.5">
                        Automatically secures profits once the daily gain target is breached.
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1 font-mono text-xs">
                        <span className="text-faint font-bold">₹</span>
                        <input
                          type="number"
                          step="1000"
                          value={profitLockAmount}
                          disabled={!profitLockActive}
                          onChange={(e) => {
                            setProfitLockAmount(e.target.value);
                            localStorage.setItem("nukebox_profit_lock_amount", e.target.value);
                          }}
                          className="w-24 rounded-xl border border-subtle bg-surface px-2.5 py-1 font-bold text-primary disabled:opacity-50"
                        />
                      </div>
                      <input
                        type="checkbox"
                        checked={profitLockActive}
                        onChange={(e) => {
                          setProfitLockActive(e.target.checked);
                          localStorage.setItem("nukebox_profit_lock_active", e.target.checked.toString());
                        }}
                        className="h-5 w-5 rounded accent-accent cursor-pointer"
                      />
                    </div>
                  </div>

                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 4: 🔌 BROKER & LIVE STREAM */}
          {activeTab === "broker" && (
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
              {/* WebSocket Telemetry Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-subtle bg-surface p-5 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-faint uppercase tracking-wider">Cloud Latency</span>
                    <Wifi className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-mono text-3xl font-black text-primary">{wsPingMs ?? "—"}</span>
                    <span className="text-xs font-bold text-faint">ms</span>
                  </div>
                  <div className="text-[11px] text-muted">Browser &harr; Dedicated VM</div>
                </div>

                <div className="rounded-2xl border border-subtle bg-surface p-5 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-faint uppercase tracking-wider">Tick Recency</span>
                    <Clock className="h-4 w-4 text-accent" />
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-mono text-3xl font-black text-primary">{latency?.avg_quote_age_ms ?? "0.0"}</span>
                    <span className="text-xs font-bold text-faint">ms</span>
                  </div>
                  <div className="text-[11px] text-muted">Min: {latency?.min_quote_age_ms ?? 0} ms</div>
                </div>

                <div className="rounded-2xl border border-subtle bg-surface p-5 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-faint uppercase tracking-wider">Subscribed Tokens</span>
                    <Layers className="h-4 w-4 text-purple-400" />
                  </div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="font-mono text-3xl font-black text-primary">{corridor?.total_tokens_subscribed ?? 192}</span>
                    <span className="text-xs font-bold text-faint">/ 192</span>
                  </div>
                  <div className="text-[11px] text-muted">3 Spots + 3 Futures + 186 Options</div>
                </div>

                <div className="rounded-2xl border border-subtle bg-surface p-5 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-faint uppercase tracking-wider">Gateway Stream</span>
                    <ShieldCheck className={`h-4 w-4 ${telemetry?.is_connected ? "text-bull" : "text-amber-400"}`} />
                  </div>
                  <div className="font-mono text-2xl font-black text-primary capitalize">{telemetry?.broker ?? "Alice Blue"}</div>
                  <div className={`text-[11px] font-bold ${telemetry?.is_connected ? "text-bull" : "text-amber-400"}`}>
                    {telemetry?.is_connected ? "● Live Stream Active" : "🌙 Keepalive Active"}
                  </div>
                </div>
              </div>

              {/* Alice Blue Gateway Card */}
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-subtle pb-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-cyan-500/15 p-2.5 text-cyan-400">
                      <Server className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-primary">Alice Blue Gateway Authentication</h3>
                      <p className="text-xs text-faint">Direct Indian Exchange WebSocket &amp; Order Execution Gateway</p>
                    </div>
                  </div>

                  {onOpenAliceLogin && (
                    <button
                      onClick={onOpenAliceLogin}
                      className="rounded-xl border border-subtle bg-surface2 hover:bg-surface3 px-3.5 py-2 text-xs font-bold text-primary transition active:scale-95"
                    >
                      Re-Authenticate OTP Handshake
                    </button>
                  )}
                </div>

                {/* Spot Indices Real-Time Status */}
                <h4 className="text-xs font-bold text-faint uppercase tracking-wider">Underlying Spot &amp; Futures Tracking</h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {["NIFTY", "SENSEX", "BANKNIFTY"].map((idx) => {
                    const data = spot[idx] || {};
                    return (
                      <div key={idx} className="rounded-2xl border border-subtle/80 bg-surface2/40 p-4">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-sm text-primary">{idx}</span>
                          <span className="rounded-full bg-bull/10 px-2 py-0.5 text-[10px] font-bold text-bull">
                            Futures Synced
                          </span>
                        </div>
                        <div className="my-2 font-mono text-2xl font-black text-primary">
                          {data.price ? Number(data.price).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
                        </div>
                        <div className="text-[11px] text-faint">
                          Cached 1M Bars: <span className="font-mono font-bold text-muted">{data.candles_count ?? 0}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 5: 🔔 SOUND & ALERTS */}
          {activeTab === "sound" && (
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-subtle pb-4">
                  <div>
                    <h2 className="text-sm font-bold text-primary flex items-center gap-2">
                      <Volume2 className="h-4 w-4 text-accent" />
                      <span>Web Audio Harmonic Synthesizer</span>
                    </h2>
                    <p className="text-xs text-faint mt-0.5">
                      Zero audio file dependencies. Synthesizes pristine tone chords directly through browser Web Audio API.
                    </p>
                  </div>

                  <button
                    onClick={handleToggleSound}
                    className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition border ${
                      soundMuted
                        ? "bg-bear/10 border-bear/30 text-bear"
                        : "bg-bull/10 border-bull/30 text-bull"
                    }`}
                  >
                    {soundMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                    <span>{soundMuted ? "Audio Muted" : "Audio Active"}</span>
                  </button>
                </div>

                {/* Master Volume Slider */}
                <div className="p-4 rounded-2xl bg-surface2/40 border border-subtle space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-primary">Master Alert Volume</span>
                    <span className="font-mono font-bold text-accent">{soundVolume}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={soundVolume}
                    disabled={soundMuted}
                    onChange={handleVolumeChange}
                    className="w-full accent-accent cursor-pointer disabled:opacity-50"
                  />
                </div>

                {/* Individual Sound Event Test Panel */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-faint uppercase tracking-wider">Preview Audio Alert Chimes</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    <div className="p-3.5 rounded-2xl bg-surface2/40 border border-subtle flex items-center justify-between">
                      <div>
                        <span className="font-bold text-xs text-primary">Order Entry</span>
                        <p className="text-faint text-[10px]">Ascending energetic double chime</p>
                      </div>
                      <button
                        onClick={() => soundEngine.playOrderEntry()}
                        className="rounded-xl border border-subtle bg-surface px-3 py-1.5 text-xs font-bold text-accent hover:bg-surface2 transition"
                      >
                        Test
                      </button>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-surface2/40 border border-subtle flex items-center justify-between">
                      <div>
                        <span className="font-bold text-xs text-primary">TSL Locked</span>
                        <p className="text-faint text-[10px]">Harmonic resonant shield tone</p>
                      </div>
                      <button
                        onClick={() => soundEngine.playTslLocked()}
                        className="rounded-xl border border-subtle bg-surface px-3 py-1.5 text-xs font-bold text-accent hover:bg-surface2 transition"
                      >
                        Test
                      </button>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-surface2/40 border border-subtle flex items-center justify-between">
                      <div>
                        <span className="font-bold text-xs text-primary">Target Hit (TP)</span>
                        <p className="text-faint text-[10px]">Triumphant major arpeggio</p>
                      </div>
                      <button
                        onClick={() => soundEngine.playTargetHit()}
                        className="rounded-xl border border-subtle bg-surface px-3 py-1.5 text-xs font-bold text-bull hover:bg-surface2 transition"
                      >
                        Test
                      </button>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-surface2/40 border border-subtle flex items-center justify-between">
                      <div>
                        <span className="font-bold text-xs text-primary">Stop-Loss Hit (SL)</span>
                        <p className="text-faint text-[10px]">Descending minor alert tone</p>
                      </div>
                      <button
                        onClick={() => soundEngine.playStopLossHit()}
                        className="rounded-xl border border-subtle bg-surface px-3 py-1.5 text-xs font-bold text-bear hover:bg-surface2 transition"
                      >
                        Test
                      </button>
                    </div>

                    <div className="p-3.5 rounded-2xl bg-surface2/40 border border-subtle flex items-center justify-between">
                      <div>
                        <span className="font-bold text-xs text-primary">Emergency Square-Off</span>
                        <p className="text-faint text-[10px]">Dual sawtooth warning buzz</p>
                      </div>
                      <button
                        onClick={() => soundEngine.playSquareOff()}
                        className="rounded-xl border border-subtle bg-surface px-3 py-1.5 text-xs font-bold text-bear hover:bg-surface2 transition"
                      >
                        Test
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 6: 💾 DATA & MAINTENANCE */}
          {activeTab === "data" && (
            <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
              <div className="rounded-3xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm space-y-5">
                <div>
                  <h2 className="text-sm font-bold text-primary flex items-center gap-2">
                    <Database className="h-4 w-4 text-accent" />
                    <span>Database &amp; Contract Cache Management</span>
                  </h2>
                  <p className="text-xs text-faint mt-0.5">
                    SQLite local candle storage inspection, contract master force-sync, and paper trade history export.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-2xl bg-surface2/40 border border-subtle space-y-3">
                    <div className="flex items-center gap-2">
                      <Download className="h-4 w-4 text-accent" />
                      <span className="font-bold text-xs text-primary">Export Paper Trade History</span>
                    </div>
                    <p className="text-faint text-[11px]">Download full ledger of all trades with execution timestamps and PnL.</p>
                    <a
                      href="/api/paper/trades/export"
                      download
                      className="inline-flex items-center justify-center rounded-xl bg-surface hover:bg-surface2 border border-subtle px-4 py-2 text-xs font-bold text-primary transition w-full"
                    >
                      Export CSV Ledger
                    </a>
                  </div>

                  <div className="p-4 rounded-2xl border border-bear/30 bg-bear/5 space-y-3">
                    <div className="flex items-center gap-2 text-bear">
                      <Trash2 className="h-4 w-4" />
                      <span className="font-bold text-xs">Reset Paper Trade History</span>
                    </div>
                    <p className="text-faint text-[11px]">Clears all closed and open paper trades in the virtual trading journal.</p>
                    <button
                      onClick={async () => {
                        if (window.confirm("Are you sure you want to reset all virtual paper trading history?")) {
                          try {
                            await fetch("/api/paper/trades/reset", { method: "POST" });
                            setActionMessage({ type: "success", text: "Paper trading history successfully reset." });
                          } catch (e) {
                            setActionMessage({ type: "error", text: `Reset failed: ${e.message}` });
                          }
                        }
                      }}
                      className="w-full rounded-xl bg-bear/20 hover:bg-bear/30 border border-bear/40 text-bear py-2 text-xs font-bold transition"
                    >
                      Clear Trade History
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </main>
      </div>

      {/* Confirmation Modal for Square Off All */}
      <AnimatePresence>
        {showConfirmModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="max-w-md w-full rounded-3xl border border-bear/30 bg-surface p-6 shadow-2xl space-y-5"
            >
              <div className="flex items-center gap-3 text-bear">
                <div className="rounded-2xl bg-bear/15 p-3">
                  <AlertTriangle className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="font-black text-lg text-primary">Emergency Square Off All?</h3>
                  <p className="text-xs text-faint">Irreversible Action</p>
                </div>
              </div>

              <p className="text-xs text-muted leading-relaxed">
                This will trigger an immediate emergency market-close across all active positions in all 44 systematic strategies. Are you certain you wish to proceed?
              </p>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowConfirmModal(false)}
                  disabled={closingAll}
                  className="rounded-xl border border-subtle bg-surface2 px-4 py-2 text-xs font-bold text-faint hover:text-primary transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSquareOffAll}
                  disabled={closingAll}
                  className="rounded-xl bg-bear hover:bg-bear/90 text-white px-5 py-2 text-xs font-bold transition shadow-lg shadow-bear/25 disabled:opacity-50"
                >
                  {closingAll ? "Closing Positions…" : "Yes, Square Off All"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
