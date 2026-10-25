export default function ScoreBar({
  label,
  value,
  threshold,
  invert = false,
  hint,
}: {
  label: string;
  value: number; // 0..1
  threshold?: number;
  invert?: boolean; // high = bad (e.g. tamper score)
  hint?: string;
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const good = invert ? value < (threshold ?? 0.3) : value >= (threshold ?? 0.9);
  const color = good ? "bg-emerald-500" : "bg-amber-500";
  return (
    <div title={hint}>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className={`font-bold ${good ? "text-emerald-300" : "text-amber-300"}`}>
          {value.toFixed(2)}
        </span>
      </div>
      <div className="relative h-2 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        {threshold !== undefined && (
          <div
            className="absolute inset-y-0 w-px bg-slate-400/70"
            style={{ left: `${threshold * 100}%` }}
            title={`threshold ${threshold}`}
          />
        )}
      </div>
    </div>
  );
}
