import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { Login } from "./components/Login";
import { TopNavbar } from "./components/TopNavbar";
import { LiveDashboardScreen } from "./screens/LiveDashboardScreen";
import { BacktestReportScreen } from "./screens/BacktestReportScreen";
import { PnlSummaryScreen } from "./screens/PnlSummaryScreen";
import { useMarketStream } from "./hooks/useMarketStream";
import { api } from "./hooks/usePaperTradingSync";
import { supabase } from "./lib/supabaseClient";

const TABS = [
  { key: "live", label: "Live", Component: LiveDashboardScreen },
  { key: "pnl", label: "P&L Summary", Component: PnlSummaryScreen },
  { key: "backtest", label: "Backtest", Component: BacktestReportScreen },
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
      />
      <main className="bg-surface2 p-3 sm:p-6">
        <div className="mx-auto max-w-6xl">
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
    </div>
  );
}

function AppInner() {
  const [user, setUser] = useState(undefined); // undefined = checking session, null = anonymous

  useEffect(() => {
    api("/api/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  async function handleLogout() {
    await api("/api/auth/logout", { method: "POST" });
    await supabase.auth.signOut();
    setUser(null);
  }

  if (user === undefined) {
    return <div className="flex min-h-screen items-center justify-center text-faint">Loading…</div>;
  }
  if (user === null) {
    return <Login onLoggedIn={setUser} />;
  }
  return <Dashboard user={user} onLogout={handleLogout} />;
}

export default function App() {
  return (
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  );
}
