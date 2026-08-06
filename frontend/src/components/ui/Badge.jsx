const VARIANTS = {
  neutral: "bg-surface3 text-muted",
  bull: "bg-bull/15 text-bull",
  bear: "bg-bear/15 text-bear",
  accent: "bg-accent/15 text-accent",
  warn: "bg-warn/15 text-warn",
};

export function Badge({ children, variant = "neutral" }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${VARIANTS[variant] ?? VARIANTS.neutral}`}>
      {children}
    </span>
  );
}
