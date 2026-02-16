import type {
  Apontamento,
  EventoMES,
  OrdemDetail,
  OrdemListItem,
  PaginatedResponse,
  Refugo,
  ResumoTempo,
  UserRole,
} from "./types";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH";
  role: UserRole;
  body?: unknown;
}

async function apiRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      "X-User-Role": options.role,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let detail = "Falha na requisicao";
    try {
      const data = (await response.json()) as { detail?: string };
      if (typeof data.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignora parse quando nao ha corpo json
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

interface ListOrdensFilters {
  page: number;
  pageSize: number;
  search?: string;
  status?: string;
}

function toQuery(filters: ListOrdensFilters): string {
  const params = new URLSearchParams();
  params.set("page", String(filters.page));
  params.set("page_size", String(filters.pageSize));
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }
  if (filters.status?.trim()) {
    params.set("status", filters.status.trim());
  }
  return params.toString();
}

export async function listOrdens(
  role: UserRole,
  filters: ListOrdensFilters
): Promise<PaginatedResponse<OrdemListItem>> {
  return apiRequest<PaginatedResponse<OrdemListItem>>(
    `/ordens-producao?${toQuery(filters)}`,
    { role }
  );
}

export async function getOrdem(role: UserRole, ordemId: number): Promise<OrdemDetail> {
  return apiRequest<OrdemDetail>(`/ordens-producao/${ordemId}`, { role });
}

interface CreateEventoPayload {
  evento: EventoMES;
  data_hora_evento?: string;
  motivo?: string;
  quantidade_produzida?: string;
}

export async function createEventoMes(
  role: UserRole,
  ordemOperacaoId: number,
  payload: CreateEventoPayload
): Promise<Apontamento> {
  return apiRequest<Apontamento>(`/mes-apontamentos/operacoes/${ordemOperacaoId}/eventos`, {
    method: "POST",
    role,
    body: payload,
  });
}

export async function listEventosMes(
  role: UserRole,
  ordemOperacaoId: number
): Promise<PaginatedResponse<Apontamento>> {
  return apiRequest<PaginatedResponse<Apontamento>>(
    `/mes-apontamentos/operacoes/${ordemOperacaoId}/eventos?page=1&page_size=50`,
    { role }
  );
}

interface CreateRefugoPayload {
  quantidade: string;
  motivo: string;
  data_hora?: string;
}

export async function createRefugoMes(
  role: UserRole,
  ordemOperacaoId: number,
  payload: CreateRefugoPayload
): Promise<Refugo> {
  return apiRequest<Refugo>(`/mes-apontamentos/operacoes/${ordemOperacaoId}/refugos`, {
    method: "POST",
    role,
    body: payload,
  });
}

export async function listRefugosMes(
  role: UserRole,
  ordemOperacaoId: number
): Promise<PaginatedResponse<Refugo>> {
  return apiRequest<PaginatedResponse<Refugo>>(
    `/mes-apontamentos/operacoes/${ordemOperacaoId}/refugos?page=1&page_size=50`,
    { role }
  );
}

export async function getResumoTempoMes(
  role: UserRole,
  ordemOperacaoId: number
): Promise<ResumoTempo> {
  return apiRequest<ResumoTempo>(
    `/mes-apontamentos/operacoes/${ordemOperacaoId}/resumo-tempo`,
    { role }
  );
}

export { ApiError };
