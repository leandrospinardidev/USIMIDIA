interface MetricProps {
  label: string;
  value: string;
}

export function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 px-2 py-1">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className="font-medium text-slate-200">{value}</p>
    </div>
  );
}
