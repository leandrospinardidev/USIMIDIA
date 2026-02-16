import { useState } from "react";

import { IndicadoresPanel } from "./components/IndicadoresPanel";
import { MesPanel } from "./components/MesPanel";
import type { UserRole } from "./types";

type ViewMode = "mes" | "indicadores";

const USER_ROLES: UserRole[] = ["operador", "pcp", "admin", "compras"];
const STATUS_FILTERS = [
  "",
  "ABERTA",
  "PLANEJADA",
  "EM_PRODUCAO",
  "PAUSADA",
  "FINALIZADA",
  "CANCELADA",
] as const;

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("mes");
  const [role, setRole] = useState<UserRole>("operador");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/90">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-slate-100">ERP Industrial Web</h1>
              <p className="mt-1 text-sm text-slate-400">
                Painel operacional com OP/MES e dashboard de indicadores.
              </p>
            </div>
            <label className="grid gap-1 text-sm">
              <span className="text-slate-400">Perfil (X-User-Role)</span>
              <select
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                value={role}
                onChange={(event) => {
                  setRole(event.target.value as UserRole);
                  setError(null);
                  setSuccess(null);
                }}
              >
                {USER_ROLES.map((userRole) => (
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
              onClick={() => setViewMode("mes")}
            >
              Operacao MES
            </button>
            <button
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                viewMode === "indicadores"
                  ? "bg-sky-600 text-white"
                  : "border border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
              }`}
              onClick={() => setViewMode("indicadores")}
            >
              Dashboard Indicadores
            </button>
          </div>
        </div>
      </header>

      <div className={viewMode === "mes" ? "block" : "hidden"}>
        <MesPanel
          role={role}
          statusFilters={STATUS_FILTERS}
          isActive={viewMode === "mes"}
          onError={setError}
          onSuccess={setSuccess}
        />
      </div>
      <div className={viewMode === "indicadores" ? "block" : "hidden"}>
        <IndicadoresPanel
          role={role}
          statusFilters={STATUS_FILTERS}
          isActive={viewMode === "indicadores"}
          onError={setError}
          onSuccess={setSuccess}
        />
      </div>

      {(error || success) && (
        <div className="fixed bottom-4 right-4 w-full max-w-sm space-y-2 px-4 lg:px-0">
          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/20 px-3 py-2 text-sm text-rose-100">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/20 px-3 py-2 text-sm text-emerald-100">
              {success}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
