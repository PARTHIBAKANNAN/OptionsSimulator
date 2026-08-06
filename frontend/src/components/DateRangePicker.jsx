const PRESETS = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "this_week", label: "This Week" },
  { key: "last_week", label: "Last Week" },
  { key: "this_month", label: "This Month" },
  { key: "30d", label: "30 Days" },
  { key: "60d", label: "60 Days" },
  { key: "90d", label: "90 Days" },
  { key: "custom", label: "Custom" },
];

export function DateRangePicker({ range, onChange, customStart, customEnd, onCustomChange }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((p) => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            range === p.key ? "bg-accent text-white" : "bg-surface3 text-muted hover:text-primary"
          }`}
        >
          {p.label}
        </button>
      ))}
      {range === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date" value={customStart} onChange={(e) => onCustomChange(e.target.value, customEnd)}
            className="rounded border border-subtle bg-surface2 px-2 py-1 text-xs"
          />
          <span className="text-faint">to</span>
          <input
            type="date" value={customEnd} onChange={(e) => onCustomChange(customStart, e.target.value)}
            className="rounded border border-subtle bg-surface2 px-2 py-1 text-xs"
          />
        </div>
      )}
    </div>
  );
}
