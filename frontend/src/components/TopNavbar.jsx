import { Activity, LineChart, Wallet, Sun, Moon, LogOut } from "lucide-react";
import { NukeBoxLogo } from "./NukeBoxLogo";

const TAB_ICONS = { live: Activity, backtest: LineChart, pnl: Wallet };

export function TopNavbar({ tabs, activeTab, onSelect, user, theme, onToggleTheme, onLogout }) {
  return (
    <nav className="sticky top-0 z-40 border-b border-subtle bg-surface/95 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1720px] items-center justify-between gap-2 px-3 sm:px-6">
        <div className="flex shrink-0 items-center">
          <NukeBoxLogo size="sm" />
        </div>

        <div className="flex min-w-0 items-center gap-1 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = TAB_ICONS[tab.key];
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => onSelect(tab.key)}
                className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl px-3 py-1.5 text-xs font-bold transition-all sm:px-4 ${
                  active
                    ? "bg-accent text-white shadow-md shadow-accent/25"
                    : "text-muted hover:bg-surface3 hover:text-primary"
                }`}
              >
                {Icon && <Icon className="h-3.5 w-3.5" />}
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <span className="hidden truncate text-xs font-medium text-faint lg:inline">{user?.email}</span>
          <button
            onClick={onToggleTheme}
            title="Toggle theme"
            className="rounded-xl border border-subtle bg-surface2 p-2 text-muted hover:bg-surface3 hover:text-primary transition"
          >
            {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
          </button>
          <button
            onClick={onLogout}
            title="Logout"
            className="rounded-xl border border-bear/20 bg-bear/10 p-2 text-bear hover:bg-bear/20 transition"
          >
            <LogOut className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </nav>
  );
}
