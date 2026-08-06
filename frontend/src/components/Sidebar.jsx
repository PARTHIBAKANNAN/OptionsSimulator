import { LiveIcon, BacktestIcon, HistoryIcon, WalletIcon, SunIcon, MoonIcon, LogoutIcon } from "./icons";

const ICONS = { live: LiveIcon, backtest: BacktestIcon, history: HistoryIcon, pnl: WalletIcon };

export function Sidebar({ tabs, activeTab, onSelect, user, theme, onToggleTheme, onLogout }) {
  return (
    <nav className="flex h-screen w-56 flex-col border-r border-subtle bg-surface">
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-sm font-bold text-accent">
          OS
        </div>
        <span className="text-sm font-semibold">OptionsSimulator</span>
      </div>

      <div className="flex-1 space-y-1 px-3">
        {tabs.map((tab) => {
          const Icon = ICONS[tab.key];
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => onSelect(tab.key)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                active ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface3 hover:text-primary"
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="space-y-2 border-t border-subtle px-3 py-3">
        <div className="truncate px-1 text-xs text-faint">{user.email}</div>
        <div className="flex gap-2">
          <button
            onClick={onToggleTheme}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-surface3 px-2 py-1.5 text-xs font-medium text-muted hover:text-primary"
          >
            {theme === "dark" ? <SunIcon className="h-3.5 w-3.5" /> : <MoonIcon className="h-3.5 w-3.5" />}
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          <button
            onClick={onLogout}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-surface3 px-2 py-1.5 text-xs font-medium text-muted hover:text-bear"
          >
            <LogoutIcon className="h-3.5 w-3.5" />
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
