export function formatNumber(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return parsed.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("pt-BR");
}

export function statusBadge(status: string): string {
  switch (status) {
    case "FINALIZADA":
    case "CONCLUIDA":
      return "bg-emerald-500/20 text-emerald-300 border-emerald-400/30";
    case "EM_PRODUCAO":
    case "EM_EXECUCAO":
      return "bg-sky-500/20 text-sky-300 border-sky-400/30";
    case "PAUSADA":
      return "bg-amber-500/20 text-amber-300 border-amber-400/30";
    case "CANCELADA":
      return "bg-rose-500/20 text-rose-300 border-rose-400/30";
    case "PLANEJADA":
    case "PENDENTE":
      return "bg-violet-500/20 text-violet-300 border-violet-400/30";
    default:
      return "bg-slate-500/20 text-slate-300 border-slate-400/30";
  }
}
