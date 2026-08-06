import { useEffect, useState } from "react";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { Login } from "./components/Login";
import { Sidebar } from "./components/Sidebar";
import { LiveDashboardScreen } from "./screens/LiveDashboardScreen";
import { BacktestReportScreen } from "./screens/BacktestReportScreen";
import { TradeHistoryScreen } from "./screens/TradeHistoryScreen";
import { PnlSummaryScreen } from "./screens/PnlSummaryScreen";
import { useMarketStream } from "./hooks/useMarketStream";
import { api } from "./hooks/usePaperTradingSync";
import { supabase } from "./lib/supabaseClient";

const TABS = [
  { key: "live", label: "Live", Component: LiveDashboardScreen },
  { key: "pnl", label: "P&L Summary", Component: PnlSummaryScreen },
  { key: "backtest", label: "Backtest", Component: BacktestReportScreen },
  { key: "history", label: "History", Component: TradeHistoryScreen },
];

function Dashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState("live");
  const { theme, toggle } = useTheme();
  useMarketStream();

  const ActiveComponent = TABS.find((t) => t.key === activeTab).Component;

  return (
    <div className="flex min-h-screen">
      <Sidebar
        tabs={TABS} activeTab={activeTab} onSelect={setActiveTab}
        user={user} theme={theme} onToggleTheme={toggle} onLogout={onLogout}
      />
      <main className="flex-1 overflow-y-auto bg-surface2 p-6">
        <div className="mx-auto max-w-6xl">
          <ActiveComponent />
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
