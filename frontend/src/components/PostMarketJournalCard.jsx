import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Award, CheckCircle2, AlertTriangle, ChevronDown, ChevronRight, RotateCw, Bot, FileText, TrendingUp, ShieldCheck } from "lucide-react";
import { api } from "../hooks/usePaperTradingSync";

export function PostMarketJournalCard() {
  const [journal, setJournal] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    api("/api/paper/intelligence/postmarket")
      .then((d) => setJournal(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleRefreshJournal() {
    setRefreshing(true);
    try {
      const res = await api("/api/paper/intelligence/postmarket/refresh", { method: "POST" });
      if (res) setJournal(res);
    } catch (e) {
      console.error("Post-market journal refresh error:", e);
    } finally {
      setRefreshing(false);
    }
  }

  if (loading || !journal) return null;

  const grade = journal.session_grade || "A";
  const isGradeGood = grade.startsWith("A") || grade.startsWith("B");
  const isGemini = journal.source?.includes("Gemini");

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-4 shadow-sm backdrop-blur-sm">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/20">
            <Award className="h-4 w-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-primary">Post-Market AI Trade Journal</h3>
              <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-extrabold border ${
                isGradeGood ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" : "bg-amber-500/15 text-amber-400 border-amber-500/30"
              }`}>
                Grade: {grade} ({journal.discipline_score}% Discipline)
              </span>
              <span className={`hidden sm:inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                isGemini ? "bg-purple-500/15 text-purple-400 border border-purple-500/30" : "bg-surface3 text-faint border border-subtle"
              }`}>
                <Bot className="h-3 w-3" />
                {journal.source || "Gemini 3.6 Flash"}
              </span>
            </div>
            <p className="text-[11px] text-faint mt-0.5">
              Daily Quantitative Execution Audit &amp; Performance Review (15:35 IST Debrief)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRefreshJournal}
            disabled={refreshing}
            title="Refresh AI Post-Market Audit"
            className="flex items-center gap-1.5 rounded-xl border border-subtle bg-surface2 px-2.5 py-1.5 text-xs font-bold text-muted hover:bg-surface3 hover:text-primary transition disabled:opacity-50"
          >
            <RotateCw className={`h-3 w-3 ${refreshing ? "animate-spin text-accent" : ""}`} />
            <span className="hidden sm:inline">{refreshing ? "Auditing..." : "Audit AI"}</span>
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-faint hover:text-primary transition p-1"
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Collapsible Content */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden space-y-4 pt-4 mt-3 border-t border-subtle/50"
          >
            {/* Executive Summary */}
            <div className="rounded-xl border border-subtle/80 bg-surface2/60 p-3.5 text-xs text-gray-300 leading-relaxed font-sans">
              <span className="font-bold text-white mr-1.5">Executive Review:</span>
              {journal.executive_summary}
            </div>

            {/* Strengths and Improvements Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-sans">
              {/* Strengths */}
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3 space-y-2">
                <div className="flex items-center gap-1.5 font-bold text-emerald-400 text-[11px] uppercase tracking-wide">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Execution Strengths</span>
                </div>
                <ul className="space-y-1.5 text-gray-300 text-[11px]">
                  {(journal.key_strengths || []).map((s, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-emerald-400 mt-0.5">•</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Areas for Improvement */}
              <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-3 space-y-2">
                <div className="flex items-center gap-1.5 font-bold text-amber-400 text-[11px] uppercase tracking-wide">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  <span>Disciplined Focus Areas</span>
                </div>
                <ul className="space-y-1.5 text-gray-300 text-[11px]">
                  {(journal.areas_for_improvement || []).map((c, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-amber-400 mt-0.5">•</span>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Tomorrow's Watchlist */}
            {journal.tomorrow_watchlist && journal.tomorrow_watchlist.length > 0 && (
              <div className="rounded-xl border border-subtle bg-surface2/40 p-3 text-xs space-y-1.5 font-sans">
                <div className="flex items-center gap-1.5 font-bold text-accent text-[11px] uppercase tracking-wide">
                  <TrendingUp className="h-3.5 w-3.5" />
                  <span>Next Session Watchlist Notes</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-gray-300">
                  {journal.tomorrow_watchlist.map((note, idx) => (
                    <div key={idx} className="flex items-start gap-1.5 rounded-lg bg-surface p-2 border border-subtle/50">
                      <span className="text-accent font-bold">#</span>
                      <span>{note}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
