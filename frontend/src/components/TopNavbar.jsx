import { Activity, LineChart, Wallet, Sun, Moon, LogOut } from "lucide-react";

const TAB_ICONS = { live: Activity, backtest: LineChart, pnl: Wallet };

// QuantMan-styled top nav: logo left, pill-style tabs center, user/theme/logout right. Replaces
// the left Sidebar -- same props/click handlers, just laid out horizontally.
export function TopNavbar({ tabs, activeTab, onSelect, user, theme, onToggleTheme, onLogout }) {
  return (
    <nav className="sticky top-0 z-40 border-b border-subtle bg-surface">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-2 sm:gap-4 sm:px-4">
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent text-sm font-bold text-white">
            OS
          </div>
          <span className="hidden text-sm font-semibold sm:inline">OptionsSimulator</span>
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto sm:justify-center">
          {tabs.map((tab) => {
            const Icon = TAB_ICONS[tab.key];
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => onSelect(tab.key)}
                className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3.5 sm:text-sm ${
                  active ? "bg-accent text-white" : "text-muted hover:bg-surface3 hover:text-primary"
                }`}
              >
                {Icon && <Icon className="h-3.5 w-3.5" />}
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex shrink-0 items-center gap-1 sm:gap-3">
          <span className="hidden truncate text-xs text-faint md:inline">{user.email}</span>
          <button
            onClick={onToggleTheme}
            title="Toggle theme"
            className="rounded-md p-1.5 text-muted hover:bg-surface3 hover:text-primary"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button
            onClick={onLogout}
            title="Logout"
            className="rounded-md p-1.5 text-muted hover:bg-surface3 hover:text-bear"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </nav>
  );
}
