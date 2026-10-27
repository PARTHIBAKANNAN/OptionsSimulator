import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { Login } from "./components/Login";
import { TopNavbar } from "./components/TopNavbar";
import { ExecutiveDashboardScreen } from "./screens/ExecutiveDashboardScreen";
import { LiveDashboardScreen } from "./screens/LiveDashboardScreen";
import { BacktestReportScreen } from "./screens/BacktestReportScreen";
import { PnlSummaryScreen } from "./screens/PnlSummaryScreen";
import { StrategyLabScreen } from "./screens/StrategyLabScreen";
import { TelemetryScreen } from "./screens/TelemetryScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { LandingScreen } from "./screens/LandingScreen";
import { useMarketStream, resyncMarketStream } from "./hooks/useMarketStream";
import { api } from "./hooks/usePaperTradingSync";
import { supabase } from "./lib/supabaseClient";
import { PullToRefresh } from "./components/PullToRefresh";

const TABS = [
  { key: "dashboard", label: "Dashboard", Component: ExecutiveDashboardScreen },
  { key: "live", label: "Live", Component: LiveDashboardScreen },
  { key: "pnl", label: "P&L Summary", Component: PnlSummaryScreen },
  { key: "backtest", label: "Backtest", Component: BacktestReportScreen },
  { key: "lab", label: "Strategy Lab", Component: StrategyLabScreen },
  { key: "telemetry", label: "WebSocket Health", Component: TelemetryScreen },
  { key: "settings", label: "Settings", Component: SettingsScreen },
];

function Dashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState("live");
  const { theme, toggle } = useTheme();
  useMarketStream();

  const ActiveComponent = TABS.find((t) => t.key === activeTab).Component;

  return (
    <div className="min-h-screen">
      <TopNavbar
        tabs={TABS} activeTab={activeTab} onSelect={setActiveTab}
        user={user} theme={theme} onToggleTheme={toggle} onLogout={onLogout}
        onRefresh={resyncMarketStream}
      />
      <PullToRefresh onRefresh={resyncMarketStream}>
        <main className="bg-surface2 p-2 sm:p-4 lg:p-6 min-h-[calc(100vh-64px)] pb-[calc(env(safe-area-inset-bottom)+4.5rem)] md:pb-6">
          <div className="mx-auto max-w-[1720px] w-full">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18 }}
              >
                <ActiveComponent />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </PullToRefresh>
    </div>
  );
}

function AppInner() {
  const [user, setUser] = useState(undefined); // undefined = checking session, null = anonymous
  const [showLoginModal, setShowLoginModal] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function initAuth() {
      const fallbackTimer = setTimeout(() => {
        if (!cancelled) setUser(null);
      }, 10000);

      try {
        // 1. First attempt existing backend session cookie
        try {
          const u = await api("/api/auth/me", { timeout: 8000 });
          if (!cancelled && u) {
            clearTimeout(fallbackTimer);
            setUser(u);
            return;
          }
        } catch {
          // Backend cookie not present, expired, or server restarted
        }

        // 2. Auto-recover from client Supabase session (stored in localStorage)
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            const u = await api("/api/auth/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ access_token: session.access_token }),
              timeout: 8000,
            });
            if (!cancelled && u) {
              clearTimeout(fallbackTimer);
              setUser(u);
              return;
            }
          }
        } catch (err) {
          console.warn("[Auth] Supabase session recovery failed:", err);
        }

        // 3. Neither backend cookie nor valid Supabase session exists
        if (!cancelled) {
          clearTimeout(fallbackTimer);
          setUser(null);
        }
      } catch {
        if (!cancelled) {
          clearTimeout(fallbackTimer);
          setUser(null);
        }
      }
    }

    initAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") {
        setUser(null);
      }
    });

    return () => {
      cancelled = true;
      subscription?.unsubscribe();
    };
  }, []);

  const [aliceAuthNotice, setAliceAuthNotice] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authCode = params.get("authCode") || params.get("auth_code") || params.get("code");
    const abSuccess = params.get("aliceblue_success");
    const abError = params.get("aliceblue_error");

    if (abSuccess) {
      setAliceAuthNotice({ type: "success", message: "Alice Blue connected & strike corridor streaming live!" });
      window.history.replaceState({}, document.title, window.location.pathname.replace(/\/callback\/?/, "/"));
      setTimeout(() => setAliceAuthNotice(null), 6000);
      return;
    }

    if (abError) {
      setAliceAuthNotice({ type: "error", message: `Alice Blue login failed: ${abError}` });
      window.history.replaceState({}, document.title, window.location.pathname.replace(/\/callback\/?/, "/"));
      setTimeout(() => setAliceAuthNotice(null), 8000);
      return;
    }

    if (authCode) {
      setAliceAuthNotice({ type: "loading", message: "Exchanging Alice Blue authCode & initializing live corridor..." });

      api("/api/auth/aliceblue/exchange", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ authCode }),
      })
        .then(() => {
          setAliceAuthNotice({ type: "success", message: "Alice Blue connected & strike corridor streaming live!" });
          window.history.replaceState({}, document.title, window.location.pathname.replace(/\/callback\/?/, "/"));
          setTimeout(() => setAliceAuthNotice(null), 6000);
        })
        .catch((err) => {
          setAliceAuthNotice({ type: "error", message: err.message || "Failed to exchange Alice Blue authCode" });
          window.history.replaceState({}, document.title, window.location.pathname.replace(/\/callback\/?/, "/"));
          setTimeout(() => setAliceAuthNotice(null), 8000);
        });
    }
  }, []);

  async function handleLogout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      // Ignore if already expired
    }
    await supabase.auth.signOut();
    setUser(null);
  }

  if (user === undefined) {
    return <div className="flex min-h-screen items-center justify-center text-faint">Loading OptionsSimulator…</div>;
  }

  if (user === null) {
    return (
      <>
        {aliceAuthNotice && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[200] max-w-md w-full px-4">
            <div className={`p-3 rounded-2xl text-xs font-bold shadow-xl border backdrop-blur-md ${
              aliceAuthNotice.type === "success"
                ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                : aliceAuthNotice.type === "error"
                ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                : "bg-blue-500/15 text-blue-300 border-blue-500/30 animate-pulse"
            }`}>
              {aliceAuthNotice.message}
            </div>
          </div>
        )}
        <LandingScreen onLoginClick={() => setShowLoginModal(true)} />
        {showLoginModal && (
          <Login
            onLoggedIn={(u) => {
              setUser(u);
              setShowLoginModal(false);
            }}
            onClose={() => setShowLoginModal(false)}
          />
        )}
      </>
    );
  }

  return (
    <>
      {aliceAuthNotice && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[200] max-w-md w-full px-4">
          <div className={`p-3 rounded-2xl text-xs font-bold shadow-xl border backdrop-blur-md ${
            aliceAuthNotice.type === "success"
              ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
              : aliceAuthNotice.type === "error"
              ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
              : "bg-blue-500/15 text-blue-300 border-blue-500/30 animate-pulse"
          }`}>
            {aliceAuthNotice.message}
          </div>
        </div>
      )}
      <Dashboard user={user} onLogout={handleLogout} />
    </>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  );
}

