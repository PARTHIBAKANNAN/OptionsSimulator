import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, TrendingUp, TrendingDown, ChevronDown, ChevronRight, Globe, Compass, Target, RotateCw, Bot } from "lucide-react";
import { api } from "../hooks/usePaperTradingSync";

function formatBriefingTime(isoStr) {
  if (!isoStr) return null;
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return null;
    const time = d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
    const date = d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    return `${date} · ${time} IST`;
  } catch {
    return null;
  }
}

export function PreMarketIntelligenceCard() {
  const [intel, setIntel] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState(null);

  useEffect(() => {
    api("/api/paper/intelligence/premarket")
      .then((d) => setIntel(d))
      .catch((e) => console.error("Pre-market fetch error:", e))
      .finally(() => setLoading(false));
  }, []);

  async function handleRefreshAI() {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      const res = await api("/api/paper/intelligence/premarket/refresh", { method: "POST" });
      if (res) {
        setIntel(res);
        setRefreshMsg("Briefing refreshed just now!");
        setTimeout(() => setRefreshMsg(null), 4000);
      }
    } catch (e) {
      console.error("AI Refresh error:", e);
      setRefreshMsg("Refresh failed: " + (e.message || "Unknown error"));
      setTimeout(() => setRefreshMsg(null), 5000);
    } finally {
      setRefreshing(false);
    }
  }

  if (loading || !intel) return null;

  const isGeminiLive = intel.source?.includes("Gemini");
  const formattedTime = formatBriefingTime(intel.generated_at);

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-4 shadow-sm backdrop-blur-sm">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-500/15 text-purple-400 border border-purple-500/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-primary">Pre-Market Catalyst Intelligence</h3>
              <span className="rounded-full bg-bull/15 px-2.5 py-0.5 text-[10px] font-extrabold text-bull border border-bull/30">
                {intel.market_bias?.replace("_", " ")} ({intel.sentiment_score}%)
              </span>
              <span className={`hidden sm:inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                isGeminiLive ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" : "bg-surface3 text-faint border border-subtle"
              }`}>
                <Bot className="h-3 w-3" />
                {intel.source || "Gemini 3.6 Flash"}
              </span>
              {formattedTime && (
                <span className="inline-flex items-center gap-1 rounded-full bg-surface2 px-2.5 py-0.5 text-[10px] font-medium text-faint border border-subtle">
                  <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
                  Last Briefing: {formattedTime}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-[11px] text-faint">
                GIFT Nifty, Global Macro &amp; Index Heavyweight Bias (08:50 AM Briefing)
              </p>
              {refreshMsg && (
                <span className={`text-[10px] font-bold ${refreshMsg.includes("failed") ? "text-bear" : "text-bull"}`}>
                  · {refreshMsg}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleRefreshAI}
            disabled={refreshing}
            title="Refresh live AI analysis"
            className="flex items-center gap-1 rounded-lg border border-subtle bg-surface2 px-2.5 py-1 text-xs font-semibold text-muted hover:bg-surface3 hover:text-primary transition disabled:opacity-50"
          >
            <RotateCw className={`h-3.5 w-3.5 text-accent ${refreshing ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">{refreshing ? "Analyzing…" : "Refresh AI"}</span>
          </button>

          <button
            onClick={() => setExpanded((v) => !v)}
            className="rounded-lg p-1.5 text-faint hover:bg-surface2 hover:text-primary transition"
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden mt-3.5 space-y-3.5"
          >
            {/* Executive Summary & Expected Gap */}
            <div className="rounded-xl border border-subtle/80 bg-surface2/80 p-3 text-xs text-primary leading-relaxed flex items-start gap-2.5">
              <Compass className="h-4 w-4 text-accent shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-accent">Expected Open: </span>
                <span className="font-semibold">{intel.expected_gap}. </span>
                <span className="text-muted">{intel.summary}</span>
              </div>
            </div>

            {/* Macro Ticker Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {intel.macro_metrics?.map((m) => (
                <div key={m.name} className="rounded-xl border border-subtle bg-surface2/50 p-2.5">
                  <div className="text-[10px] font-bold text-faint uppercase">{m.name}</div>
                  <div className="font-mono text-xs font-extrabold text-primary mt-0.5">{m.value}</div>
                  <div className={`font-mono text-[10px] font-semibold mt-0.5 ${m.status === "bull" ? "text-bull" : "text-bear"}`}>
                    {m.change}
                  </div>
                </div>
              ))}
            </div>

            {/* Bottom Split: Sector Bias & Strategy Focus */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-xs">
              {/* Sector Sentiment */}
              <div className="rounded-xl border border-subtle bg-surface2/50 p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-faint">
                  <Globe className="h-3.5 w-3.5 text-accent" /> Key Sector Sentiment
                </div>
                <div className="space-y-1.5">
                  {intel.sector_biases?.map((s) => (
                    <div key={s.sector} className="flex items-start justify-between gap-2 py-0.5 border-b border-subtle/40 last:border-0">
                      <div>
                        <span className="font-bold text-primary">{s.sector}: </span>
                        <span className="text-muted text-[11px]">{s.catalyst}</span>
                      </div>
                      <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold ${
                        s.bias === "BULLISH"
                          ? "bg-bull/15 text-bull"
                          : s.bias === "NEUTRAL"
                          ? "bg-surface3 text-muted"
                          : "bg-bear/15 text-bear"
                      }`}>
                        {s.bias}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recommended Strategy Conviction */}
              <div className="rounded-xl border border-subtle bg-surface2/50 p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-faint">
                  <Target className="h-3.5 w-3.5 text-bull" /> Opening Strategy Focus
                </div>
                <div className="space-y-1.5">
                  {intel.recommended_strategies?.map((strat) => (
                    <div key={strat.name} className="flex items-start justify-between gap-2 py-0.5 border-b border-subtle/40 last:border-0">
                      <div>
                        <div className="font-bold text-primary font-mono text-[11px]">{strat.name}</div>
                        <div className="text-[10px] text-faint">{strat.reason}</div>
                      </div>
                      <span className="shrink-0 rounded bg-bull/15 px-1.5 py-0.5 text-[9px] font-extrabold text-bull">
                        {strat.conviction}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
