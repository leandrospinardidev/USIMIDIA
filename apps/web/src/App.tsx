import { useState } from "react";

import { AppTopbar } from "./components/AppTopbar";
import { IndicadoresPanel } from "./components/IndicadoresPanel";
import { MesPanel } from "./components/MesPanel";
import type { UserRole } from "./types";
import type { AppViewMode } from "./components/AppTopbar";

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
  const [viewMode, setViewMode] = useState<AppViewMode>("mes");
  const [role, setRole] = useState<UserRole>("operador");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <AppTopbar
        role={role}
        userRoles={USER_ROLES}
        viewMode={viewMode}
        onRoleChange={(nextRole) => {
          setRole(nextRole);
          setError(null);
          setSuccess(null);
        }}
        onViewModeChange={setViewMode}
      />

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
