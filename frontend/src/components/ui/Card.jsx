export function Card({ title, children, className = "" }) {
  return (
    <div className={`rounded-lg border border-subtle bg-surface ${className}`}>
      {title && (
        <div className="border-b border-subtle px-4 py-2 text-sm font-medium text-muted">
          {title}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
