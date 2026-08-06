// Small hand-rolled stroke icons — no icon library dependency, same "roll it by hand" approach
// already used for charts (see EquityCurveChart.jsx).
function Icon({ children, className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
         strokeLinecap="round" strokeLinejoin="round" className={className}>
      {children}
    </svg>
  );
}

export function LiveIcon(props) {
  return <Icon {...props}><path d="M3 17l5-6 4 4 5-8 4 5" /></Icon>;
}

export function BacktestIcon(props) {
  return <Icon {...props}><path d="M12 3a9 9 0 1 0 9 9" /><path d="M12 3v9l6 3" /></Icon>;
}

export function HistoryIcon(props) {
  return <Icon {...props}><circle cx="12" cy="13" r="7" /><path d="M12 10v3l2 2M9 3h6M9 3l1 3M15 3l-1 3" /></Icon>;
}

export function WalletIcon(props) {
  return <Icon {...props}><rect x="3" y="7" width="18" height="12" rx="2" /><path d="M3 10h18M15 15h2" /></Icon>;
}

export function SunIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Icon>
  );
}

export function MoonIcon(props) {
  return <Icon {...props}><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" /></Icon>;
}

export function LogoutIcon(props) {
  return <Icon {...props}><path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M16 17l4-5-4-5M20 12H9" /></Icon>;
}

export function ChevronDownIcon(props) {
  return <Icon {...props}><path d="M6 9l6 6 6-6" /></Icon>;
}

export function DownloadIcon(props) {
  return <Icon {...props}><path d="M12 3v12M7 10l5 5 5-5M4 20h16" /></Icon>;
}
