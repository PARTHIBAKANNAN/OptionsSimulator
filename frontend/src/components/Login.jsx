import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Lock, Mail, ArrowRight, ShieldCheck } from "lucide-react";
import { supabase } from "../lib/supabaseClient";
import { api } from "../hooks/usePaperTradingSync";

export function Login({ onLoggedIn, onClose }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data, error: supaError } = await supabase.auth.signInWithPassword({ email, password });
      if (supaError) throw supaError;
      const user = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_token: data.session.access_token }),
      });
      onLoggedIn(user);
    } catch (err) {
      setError(err.message || "Failed to sign in. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  }

  const content = (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: 10 }}
      className="relative w-full max-w-md rounded-3xl border border-subtle bg-surface/95 p-6 sm:p-8 shadow-2xl backdrop-blur-2xl"
      onClick={(e) => e.stopPropagation()}
    >
      {onClose && (
        <button
          onClick={onClose}
          className="absolute top-5 right-5 rounded-full p-2 text-faint hover:bg-surface2 hover:text-primary transition"
        >
          <X className="h-4 w-4" />
        </button>
      )}

      {/* Header */}
      <div className="mb-6 space-y-2">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-accent to-indigo-500 text-white shadow-lg shadow-accent/25">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-black text-primary tracking-tight">Quant Terminal Login</h2>
        <p className="text-xs text-faint">
          Authorized quantitative credentials required to access the execution terminal.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-bear/30 bg-bear/10 p-3 text-xs font-semibold text-bear">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-muted">
            Operator Email
          </label>
          <div className="relative">
            <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-faint" />
            <input
              type="email"
              placeholder="quant@optionssimulator.internal"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-subtle bg-surface2 pl-10 pr-4 py-2.5 text-xs text-primary placeholder:text-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              required
            />
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-muted">
            Access Password
          </label>
          <div className="relative">
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-faint" />
            <input
              type="password"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-subtle bg-surface2 pl-10 pr-4 py-2.5 text-xs text-primary placeholder:text-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 text-xs font-black text-white hover:brightness-110 shadow-lg shadow-accent/25 transition disabled:opacity-50"
        >
          <span>{loading ? "Authenticating Session…" : "Launch Terminal"}</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>

        <div className="pt-2 text-center text-[11px] text-faint">
          <span>Need access? </span>
          <a
            href="mailto:access@optionssimulator.internal?subject=Access%20Request%20for%20OptionsSimulator%20Quant%20Terminal"
            className="font-bold text-accent hover:underline"
          >
            Contact Administrator
          </a>
        </div>
      </form>
    </motion.div>
  );

  if (onClose) {
    return (
      <div
        onClick={onClose}
        className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md"
      >
        {content}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      {content}
    </div>
  );
}
