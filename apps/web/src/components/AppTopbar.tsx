import type { UserRole } from "../types";

export type AppViewMode = "mes" | "indicadores" | "orcamentos";

interface AppTopbarProps {
  role: UserRole;
  userRoles: readonly UserRole[];
  viewMode: AppViewMode;
  onRoleChange: (role: UserRole) => void;
  onViewModeChange: (mode: AppViewMode) => void;
}

export function AppTopbar({
  role,
  userRoles,
  viewMode,
  onRoleChange,
  onViewModeChange,
}: AppTopbarProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-900/90">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">ERP Industrial Web</h1>
            <p className="mt-1 text-sm text-slate-400">
              Painel operacional com OP/MES, indicadores e gerador de orcamentos.
            </p>
          </div>
          <label className="grid gap-1 text-sm">
            <span className="text-slate-400">Perfil (X-User-Role)</span>
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
              value={role}
              onChange={(event) => onRoleChange(event.target.value as UserRole)}
            >
              {userRoles.map((userRole) => (
                <option key={userRole} value={userRole}>
                  {userRole}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex gap-2">
          <button
            className={`rounded-md px-3 py-2 text-sm font-medium ${
              viewMode === "mes"
                ? "bg-sky-600 text-white"
                : "border border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
            }`}
            onClick={() => onViewModeChange("mes")}
          >
            Operacao MES
          </button>
          <button
            className={`rounded-md px-3 py-2 text-sm font-medium ${
              viewMode === "indicadores"
                ? "bg-sky-600 text-white"
                : "border border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
            }`}
            onClick={() => onViewModeChange("indicadores")}
          >
            Dashboard Indicadores
          </button>
          <button
            className={`rounded-md px-3 py-2 text-sm font-medium ${
              viewMode === "orcamentos"
                ? "bg-sky-600 text-white"
                : role === "operador"
                  ? "cursor-not-allowed border border-slate-800 bg-slate-900 text-slate-500"
                  : "border border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
            }`}
            onClick={() => {
              if (role === "operador") {
                return;
              }
              onViewModeChange("orcamentos");
            }}
            disabled={role === "operador"}
            title={
              role === "operador"
                ? "Gerador de orcamentos requer perfil admin, pcp ou compras."
                : undefined
            }
          >
            Gerador Orcamentos
          </button>
        </div>
        {role === "operador" && (
          <p className="text-xs text-amber-300/80">
            O gerador de orcamentos exige perfil admin, pcp ou compras.
          </p>
        )}
      </div>
    </header>
  );
}
