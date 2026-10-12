import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck, Lock, KeyRound, AlertCircle, RefreshCw, X, Zap, Eye, EyeOff } from "lucide-react";
import { API_BASE } from "../lib/apiBase";

export function ConnectAliceBlueModal({ isOpen, onClose, onConnected }) {
  const [userId, setUserId] = useState("2628887");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [totp, setTotp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const totpRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccess(false);
      setTimeout(() => totpRef.current?.focus(), 150);
    }
  }, [isOpen]);

  async function handleSubmit(e) {
    e?.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/auth/aliceblue/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId.trim(),
          password: password.trim(),
          totp: totp.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || "Authentication failed");
      }

      setSuccess(true);
      if (onConnected) onConnected();
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      setError(err.message || "Failed to authenticate with Alice Blue");
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  return createPortal(
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          className="relative w-full max-w-sm rounded-2xl border border-subtle bg-surface p-5 shadow-2xl z-10"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-3 border-b border-subtle">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                <ShieldCheck size={18} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-primary">Alice Blue Login</h3>
                <p className="text-[11px] text-faint">Direct daily TOTP session authorization</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1 text-faint hover:bg-surface2 hover:text-primary transition"
            >
              <X size={16} />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-3.5 pt-4">
            {/* User ID */}
            <div>
              <label className="block text-[11px] font-semibold text-muted mb-1">
                Client ID (UCC)
              </label>
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value.toUpperCase())}
                placeholder="2628887"
                className="w-full rounded-xl border border-subtle bg-surface2 px-3 py-2 text-xs text-primary font-mono focus:border-accent focus:outline-none"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-[11px] font-semibold text-muted mb-1">
                Password <span className="text-faint font-normal">(leave blank for .env default)</span>
              </label>
              <div className="relative">
                <Lock size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
                <input
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-xl border border-subtle bg-surface2 pl-8 pr-9 py-2 text-xs text-primary placeholder-faint focus:border-accent focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-faint hover:text-muted transition"
                >
                  {showPwd ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
              </div>
            </div>

            {/* 6-Digit TOTP */}
            <div>
              <label className="block text-[11px] font-semibold text-muted mb-1">
                TOTP Code <span className="text-faint font-normal">(auto-generated if blank)</span>
              </label>
              <div className="relative">
                <KeyRound size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
                <input
                  ref={totpRef}
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={totp}
                  onChange={(e) => setTotp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="6-digit TOTP"
                  className="w-full rounded-xl border border-subtle bg-surface2 pl-8 pr-3 py-2 text-xs text-primary font-mono tracking-widest focus:border-accent focus:outline-none"
                />
              </div>
            </div>

            {/* Info note */}
            <div className="flex items-start gap-2 rounded-xl border border-blue-500/15 bg-blue-500/5 px-3 py-2">
              <Zap size={13} className="text-blue-400 shrink-0 mt-0.5" />
              <p className="text-[10px] text-blue-300/80 leading-relaxed">
                Provide your morning authenticator code. If left blank, your backend will auto-generate it using configured TOTP secret.
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-lg bg-bear/10 border border-bear/20 p-2.5 text-xs text-bear">
                <AlertCircle size={14} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="flex items-center gap-2 rounded-lg bg-bull/10 border border-bull/20 p-2.5 text-xs text-bull">
                <ShieldCheck size={14} className="shrink-0" />
                <span>Alice Blue session authorized! Streaming live.</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || success}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-xs font-bold text-white shadow-lg shadow-blue-500/20 transition disabled:opacity-50 mt-1 cursor-pointer"
            >
              {loading ? (
                <>
                  <RefreshCw size={13} className="animate-spin" />
                  <span>Connecting Alice Blue...</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={14} />
                  <span>Authorize & Stream</span>
                </>
              )}
            </button>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>,
    document.body
  );
}
