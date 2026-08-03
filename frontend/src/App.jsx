import { useEffect, useState } from "react";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import { Login } from "./components/Login";
import { LiveDashboardScreen } from "./screens/LiveDashboardScreen";
import { BacktestReportScreen } from "./screens/BacktestReportScreen";
import { TradeHistoryScreen } from "./screens/TradeHistoryScreen";
import { useMarketStream } from "./hooks/useMarketStream";
import { api } from "./hooks/usePaperTradingSync";
import { supabase } from "./lib/supabaseClient";

const TABS = [
  { key: "live", label: "Live", Component: LiveDashboardScreen },
  { key: "backtest", label: "Backtest", Component: BacktestReportScreen },
  { key: "history", label: "History", Component: TradeHistoryScreen },
];

function Dashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState("live");
  const { theme, toggle } = useTheme();
  useMarketStream();

  const ActiveComponent = TABS.find((t) => t.key === activeTab).Component;

  return (
    <div className="min-h-screen">
      <nav className="flex items-center justify-between border-b border-subtle bg-surface px-4 py-3">
        <div className="flex items-center gap-4">
          <span className="font-semibold">OptionsSimulator</span>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={activeTab === tab.key ? "text-sm font-medium text-primary" : "text-sm text-muted"}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-faint">{user.email}</span>
          <button onClick={toggle} className="text-muted">{theme === "dark" ? "Light" : "Dark"}</button>
          <button onClick={onLogout} className="text-muted">Logout</button>
        </div>
      </nav>
      <main className="mx-auto max-w-5xl p-4">
        <ActiveComponent />
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
