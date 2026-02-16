interface MetricProps {
  label: string;
  value: string;
}

export function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-md border border-slate-700/80 bg-slate-900/80 px-2.5 py-2 shadow-sm shadow-cyan-950/30">
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="font-semibold text-slate-100">{value}</p>
    </div>
  );
}
