import { useState } from "react";
import { 
  Activity, 
  LineChart, 
  Wallet, 
  Sun, 
  Moon, 
  LogOut, 
  LayoutDashboard, 
  FlaskConical, 
  Wifi, 
  Menu, 
  X,
  ChevronRight,
  ShieldCheck
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { NukeBoxLogo } from "./NukeBoxLogo";

const TAB_ICONS = {
  dashboard: LayoutDashboard,
  live: Activity,
  pnl: Wallet,
  backtest: LineChart,
  lab: FlaskConical,
  telemetry: Wifi,
};

// Primary 4 tabs displayed on mobile bottom bar
const MOBILE_BOTTOM_TABS = ["live", "dashboard", "pnl", "telemetry"];

export function TopNavbar({ tabs, activeTab, onSelect, user, theme, onToggleTheme, onLogout }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Top Header Navbar */}
      <nav className="sticky top-0 z-40 border-b border-subtle bg-surface/95 backdrop-blur-md pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-14 max-w-[1720px] items-center justify-between gap-2 px-3 sm:px-6">
          <div className="flex shrink-0 items-center">
            <NukeBoxLogo size="sm" />
          </div>

          {/* Desktop Tab Row (Preserved 100% untouched for desktop browser) */}
          <div className="hidden md:flex min-w-0 items-center gap-1 overflow-x-auto">
            {tabs.map((tab) => {
              const Icon = TAB_ICONS[tab.key] || Activity;
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
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Right Action Icons */}
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

      {/* Mobile Bottom Navigation Bar (iOS / Android Native Pattern) */}
      <div className="fixed bottom-0 left-0 right-0 z-50 md:hidden border-t border-subtle bg-surface/95 backdrop-blur-xl pb-[env(safe-area-inset-bottom)] shadow-2xl">
        <div className="flex h-14 items-center justify-around px-2">
          {MOBILE_BOTTOM_TABS.map((key) => {
            const tab = tabs.find((t) => t.key === key);
            if (!tab) return null;
            const Icon = TAB_ICONS[key] || Activity;
            const active = activeTab === key;

            return (
              <button
                key={key}
                onClick={() => {
                  onSelect(key);
                  setMobileMenuOpen(false);
                }}
                className={`flex flex-col items-center justify-center flex-1 py-1 transition ${
                  active ? "text-accent font-bold" : "text-faint hover:text-primary font-medium"
                }`}
              >
                <div className={`p-1 rounded-xl transition ${active ? "bg-accent/15" : ""}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <span className="text-[10px] mt-0.5 tracking-tight">{tab.label.split(" ")[0]}</span>
              </button>
            );
          })}

          {/* Mobile "More" Drawer Trigger */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className={`flex flex-col items-center justify-center flex-1 py-1 transition ${
              mobileMenuOpen || !MOBILE_BOTTOM_TABS.includes(activeTab)
                ? "text-accent font-bold"
                : "text-faint hover:text-primary font-medium"
            }`}
          >
            <div className={`p-1 rounded-xl transition ${mobileMenuOpen ? "bg-accent/15" : ""}`}>
              <Menu className="h-4 w-4" />
            </div>
            <span className="text-[10px] mt-0.5 tracking-tight">More</span>
          </button>
        </div>
      </div>

      {/* Mobile Drawer (Bottom Sheet) for Backtest, Strategy Lab & Account */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileMenuOpen(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />

            {/* Bottom Sheet */}
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 250 }}
              className="absolute bottom-0 left-0 right-0 rounded-t-3xl border-t border-subtle bg-surface p-5 pb-[calc(env(safe-area-inset-bottom)+5rem)] shadow-2xl max-h-[80vh] overflow-y-auto"
            >
              {/* Drag Handle */}
              <div className="mx-auto mb-4 h-1 w-12 rounded-full bg-subtle" />

              <div className="flex items-center justify-between mb-4 border-b border-subtle pb-3">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/15 text-accent">
                    <NukeBoxLogo size="xs" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-primary">All Modules</div>
                    <div className="text-[10px] text-faint truncate max-w-[200px]">{user?.email || "Signed In"}</div>
                  </div>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-full p-1.5 text-faint hover:bg-surface2 hover:text-primary"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Grid of All Tabs */}
              <div className="grid grid-cols-2 gap-2 mb-4">
                {tabs.map((tab) => {
                  const Icon = TAB_ICONS[tab.key] || Activity;
                  const active = activeTab === tab.key;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => {
                        onSelect(tab.key);
                        setMobileMenuOpen(false);
                      }}
                      className={`flex items-center gap-2.5 rounded-2xl p-3 text-left transition border ${
                        active
                          ? "bg-accent/15 border-accent text-accent font-bold shadow-sm"
                          : "bg-surface2/60 border-subtle text-primary hover:bg-surface3"
                      }`}
                    >
                      <div className={`p-2 rounded-xl ${active ? "bg-accent text-white" : "bg-surface3 text-faint"}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-bold truncate">{tab.label}</div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Status footer */}
              <div className="rounded-xl border border-subtle/80 bg-surface2/40 p-3 text-center text-[10px] text-faint flex items-center justify-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-bull" />
                <span>NukeBox Autonomous Quantitative Derivatives</span>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
