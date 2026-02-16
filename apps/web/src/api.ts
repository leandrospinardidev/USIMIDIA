import type {
  Apontamento,
  BomListItem,
  CentroTrabalhoCadastro,
  ClienteCadastro,
  EventoMES,
  IndicadorOrdemItem,
  KpisGerais,
  OrcamentoAnexo,
  OrcamentoDetail,
  OrcamentoListItem,
  OrcamentoOperacaoInput,
  OrcamentoPresetCnc,
  OrcamentoPresetHistoricoItem,
  OrcamentoPresetRankingItem,
  OrcamentoPresetRegistroUso,
  OrcamentoPresetRecalibracao,
  OrcamentoPresetSugestao,
  OrcamentoPdfSimulacao,
  OrcamentoSimulacao,
  OrdemDetail,
  OrdemListItem,
  PaginatedResponse,
  ProdutoFinalCadastro,
  Refugo,
  RastreabilidadeOrdem,
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
  method?: "GET" | "POST" | "PATCH" | "DELETE";
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

async function apiRequestForm<T>(
  path: string,
  options: { method?: "POST" | "PATCH"; role: UserRole; formData: FormData }
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "POST",
    headers: {
      "X-User-Role": options.role,
    },
    body: options.formData,
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

  return (await response.json()) as T;
}

interface ListOrdensFilters {
  page: number;
  pageSize: number;
  search?: string;
  status?: string;
}

function toQuery(filters: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null) {
      continue;
    }
    const normalized = String(value).trim();
    if (!normalized) {
      continue;
    }
    params.set(key, normalized);
  }
  return params.toString();
}

export async function listOrdens(
  role: UserRole,
  filters: ListOrdensFilters
): Promise<PaginatedResponse<OrdemListItem>> {
  const query = toQuery({
    page: filters.page,
    page_size: filters.pageSize,
    search: filters.search,
    status: filters.status,
  });
  return apiRequest<PaginatedResponse<OrdemListItem>>(
    `/ordens-producao?${query}`,
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

interface IndicadoresFilters {
  page: number;
  pageSize: number;
  search?: string;
  status?: string;
  periodoInicio?: string;
  periodoFim?: string;
}

export async function getIndicadoresKpis(
  role: UserRole,
  filters: Omit<IndicadoresFilters, "page" | "pageSize" | "search">
): Promise<KpisGerais> {
  const query = toQuery({
    periodo_inicio: filters.periodoInicio,
    periodo_fim: filters.periodoFim,
    status: filters.status,
  });
  return apiRequest<KpisGerais>(`/indicadores/kpis?${query}`, { role });
}

export async function listIndicadoresOrdens(
  role: UserRole,
  filters: IndicadoresFilters
): Promise<PaginatedResponse<IndicadorOrdemItem>> {
  const query = toQuery({
    page: filters.page,
    page_size: filters.pageSize,
    search: filters.search,
    status: filters.status,
    periodo_inicio: filters.periodoInicio,
    periodo_fim: filters.periodoFim,
  });
  return apiRequest<PaginatedResponse<IndicadorOrdemItem>>(
    `/indicadores/ordens?${query}`,
    { role }
  );
}

export async function getRastreabilidadeOrdem(
  role: UserRole,
  ordemId: number
): Promise<RastreabilidadeOrdem> {
  return apiRequest<RastreabilidadeOrdem>(`/indicadores/rastreabilidade/ordens/${ordemId}`, {
    role,
  });
}

interface ListOrcamentosFilters {
  page: number;
  pageSize: number;
  search?: string;
  status?: string;
}

interface ListOrcamentoPresetsFilters {
  page: number;
  pageSize: number;
  ativo?: boolean;
  clienteId?: number;
  produtoFinalId?: number;
  search?: string;
}

interface OrcamentoPresetRankingFilters {
  limit?: number;
  clienteId?: number;
  produtoFinalId?: number;
  centroTrabalhoId?: number;
  materialReferencia?: string;
  familiaPeca?: string;
  tipoPeca?: string;
}

interface OrcamentoPresetSugestaoFilters {
  clienteId?: number;
  produtoFinalId?: number;
  centroTrabalhoId?: number;
  materialReferencia?: string;
  familiaPeca?: string;
  tipoPeca?: string;
}

interface OrcamentoCalculoPayload {
  cliente_id?: number;
  produto_final_id: number;
  bom_id?: number;
  preset_cnc_id?: number;
  quantidade: string;
  margem_lucro_pct?: string;
  custo_indireto_fixo?: string;
  custo_indireto_pct?: string;
  operacoes?: OrcamentoOperacaoInput[];
}

interface OrcamentoCreatePayload extends OrcamentoCalculoPayload {
  codigo?: string;
  referencia_projeto?: string;
  observacao?: string;
  moeda?: string;
}

interface OrcamentoPresetOperacaoTemplatePayload {
  sequencia: number;
  centro_trabalho_id?: number;
  setup_min?: string;
  ciclo_min?: string;
  descricao?: string;
}

interface OrcamentoPresetCncCreatePayload {
  codigo?: string;
  nome: string;
  descricao?: string;
  ativo?: boolean;
  cliente_id?: number;
  produto_final_id?: number;
  centro_trabalho_id?: number;
  fabricante_referencia?: string;
  linha_maquina_referencia?: string;
  perfil_maquina?: string;
  familia_peca?: string;
  tipo_peca?: string;
  material_referencia?: string;
  operacao_principal?: string;
  diametro_referencia_mm?: string;
  comprimento_referencia_mm?: string;
  fator_ciclo?: string;
  fator_setup?: string;
  margem_lucro_pct?: string;
  custo_indireto_pct?: string;
  operacoes_template?: OrcamentoPresetOperacaoTemplatePayload[];
  heuristicas?: Record<string, unknown>;
  motivo_versao?: string;
}

interface OrcamentoPresetCncUpdatePayload extends Partial<OrcamentoPresetCncCreatePayload> {}

interface OrcamentoPresetRecalibrarPayload {
  janela_dias?: number;
  centro_trabalho_id?: number;
  produto_final_id?: number;
  suavizacao_alpha?: string;
  motivo_versao?: string;
}

interface OrcamentoPresetRegistrarUsoPayload {
  tipo_evento?: string;
  erro_previsao_pct?: string;
  observacao?: string;
}

export async function listClientesCadastro(
  role: UserRole
): Promise<PaginatedResponse<ClienteCadastro>> {
  return apiRequest<PaginatedResponse<ClienteCadastro>>(
    "/cadastro/clientes?page=1&page_size=200&ativo=true",
    { role }
  );
}

export async function listProdutosCadastro(
  role: UserRole
): Promise<PaginatedResponse<ProdutoFinalCadastro>> {
  return apiRequest<PaginatedResponse<ProdutoFinalCadastro>>(
    "/cadastro/produtos-finais?page=1&page_size=200&ativo=true",
    { role }
  );
}

export async function listCentrosCadastro(
  role: UserRole
): Promise<PaginatedResponse<CentroTrabalhoCadastro>> {
  return apiRequest<PaginatedResponse<CentroTrabalhoCadastro>>(
    "/cadastro/centros-trabalho?page=1&page_size=200&ativo=true",
    { role }
  );
}

export async function listBomsByProduto(
  role: UserRole,
  produtoFinalId: number
): Promise<PaginatedResponse<BomListItem>> {
  return apiRequest<PaginatedResponse<BomListItem>>(
    `/engenharia-bom/boms?page=1&page_size=200&produto_final_id=${produtoFinalId}`,
    { role }
  );
}

export async function simularOrcamento(
  role: UserRole,
  payload: OrcamentoCalculoPayload
): Promise<OrcamentoSimulacao> {
  return apiRequest<OrcamentoSimulacao>("/orcamentos/simulacoes", {
    method: "POST",
    role,
    body: payload,
  });
}

interface OrcamentoPdfSimulacaoPayload {
  centro_trabalho_id: number;
  file: File;
  margem_lucro_pct?: string;
  custo_indireto_fixo?: string;
  custo_indireto_pct?: string;
  quantidade_override?: number;
}

export async function simularOrcamentoPorPdf(
  role: UserRole,
  payload: OrcamentoPdfSimulacaoPayload
): Promise<OrcamentoPdfSimulacao> {
  const formData = new FormData();
  formData.append("centro_trabalho_id", String(payload.centro_trabalho_id));
  formData.append("file", payload.file);
  if (payload.margem_lucro_pct?.trim()) {
    formData.append("margem_lucro_pct", payload.margem_lucro_pct.trim());
  }
  if (payload.custo_indireto_fixo?.trim()) {
    formData.append("custo_indireto_fixo", payload.custo_indireto_fixo.trim());
  }
  if (payload.custo_indireto_pct?.trim()) {
    formData.append("custo_indireto_pct", payload.custo_indireto_pct.trim());
  }
  if (payload.quantidade_override && payload.quantidade_override > 0) {
    formData.append("quantidade_override", String(payload.quantidade_override));
  }
  return apiRequestForm<OrcamentoPdfSimulacao>("/orcamentos/simulacoes/pdf", {
    method: "POST",
    role,
    formData,
  });
}

export async function criarOrcamento(
  role: UserRole,
  payload: OrcamentoCreatePayload
): Promise<OrcamentoDetail> {
  return apiRequest<OrcamentoDetail>("/orcamentos", {
    method: "POST",
    role,
    body: payload,
  });
}

export async function listOrcamentos(
  role: UserRole,
  filters: ListOrcamentosFilters
): Promise<PaginatedResponse<OrcamentoListItem>> {
  const query = toQuery({
    page: filters.page,
    page_size: filters.pageSize,
    search: filters.search,
    status: filters.status,
  });
  return apiRequest<PaginatedResponse<OrcamentoListItem>>(`/orcamentos?${query}`, { role });
}

export async function listOrcamentoPresetsCnc(
  role: UserRole,
  filters: ListOrcamentoPresetsFilters
): Promise<PaginatedResponse<OrcamentoPresetCnc>> {
  const query = toQuery({
    page: filters.page,
    page_size: filters.pageSize,
    ativo: filters.ativo === undefined ? undefined : String(filters.ativo),
    cliente_id: filters.clienteId,
    produto_final_id: filters.produtoFinalId,
    search: filters.search,
  });
  return apiRequest<PaginatedResponse<OrcamentoPresetCnc>>(`/orcamentos/presets-cnc?${query}`, {
    role,
  });
}

export async function createOrcamentoPresetCnc(
  role: UserRole,
  payload: OrcamentoPresetCncCreatePayload
): Promise<OrcamentoPresetCnc> {
  return apiRequest<OrcamentoPresetCnc>("/orcamentos/presets-cnc", {
    method: "POST",
    role,
    body: payload,
  });
}

export async function updateOrcamentoPresetCnc(
  role: UserRole,
  presetId: number,
  payload: OrcamentoPresetCncUpdatePayload
): Promise<OrcamentoPresetCnc> {
  return apiRequest<OrcamentoPresetCnc>(`/orcamentos/presets-cnc/${presetId}`, {
    method: "PATCH",
    role,
    body: payload,
  });
}

export async function recalibrarOrcamentoPresetCnc(
  role: UserRole,
  presetId: number,
  payload: OrcamentoPresetRecalibrarPayload
): Promise<OrcamentoPresetRecalibracao> {
  return apiRequest<OrcamentoPresetRecalibracao>(
    `/orcamentos/presets-cnc/${presetId}/recalibrar-mes`,
    {
      method: "POST",
      role,
      body: payload,
    }
  );
}

export async function registrarUsoOrcamentoPresetCnc(
  role: UserRole,
  presetId: number,
  payload: OrcamentoPresetRegistrarUsoPayload
): Promise<OrcamentoPresetRegistroUso> {
  return apiRequest<OrcamentoPresetRegistroUso>(`/orcamentos/presets-cnc/${presetId}/registrar-uso`, {
    method: "POST",
    role,
    body: payload,
  });
}

export async function listOrcamentoPresetHistorico(
  role: UserRole,
  presetId: number
): Promise<PaginatedResponse<OrcamentoPresetHistoricoItem>> {
  return apiRequest<PaginatedResponse<OrcamentoPresetHistoricoItem>>(
    `/orcamentos/presets-cnc/${presetId}/historico?page=1&page_size=20`,
    { role }
  );
}

export async function listOrcamentoPresetsRanking(
  role: UserRole,
  filters: OrcamentoPresetRankingFilters
): Promise<{ items: OrcamentoPresetRankingItem[] }> {
  const query = toQuery({
    limit: filters.limit ?? 8,
    cliente_id: filters.clienteId,
    produto_final_id: filters.produtoFinalId,
    centro_trabalho_id: filters.centroTrabalhoId,
    material_referencia: filters.materialReferencia,
    familia_peca: filters.familiaPeca,
    tipo_peca: filters.tipoPeca,
  });
  return apiRequest<{ items: OrcamentoPresetRankingItem[] }>(
    `/orcamentos/presets-cnc/ranking?${query}`,
    { role }
  );
}

export async function getOrcamentoPresetSugestao(
  role: UserRole,
  filters: OrcamentoPresetSugestaoFilters
): Promise<OrcamentoPresetSugestao> {
  const query = toQuery({
    cliente_id: filters.clienteId,
    produto_final_id: filters.produtoFinalId,
    centro_trabalho_id: filters.centroTrabalhoId,
    material_referencia: filters.materialReferencia,
    familia_peca: filters.familiaPeca,
    tipo_peca: filters.tipoPeca,
  });
  return apiRequest<OrcamentoPresetSugestao>(`/orcamentos/presets-cnc/sugestao?${query}`, { role });
}

export async function getOrcamento(
  role: UserRole,
  orcamentoId: number
): Promise<OrcamentoDetail> {
  return apiRequest<OrcamentoDetail>(`/orcamentos/${orcamentoId}`, { role });
}

export async function uploadOrcamentoAnexo(
  role: UserRole,
  orcamentoId: number,
  file: File,
  observacao?: string
): Promise<OrcamentoAnexo> {
  const formData = new FormData();
  formData.append("file", file);
  if (observacao?.trim()) {
    formData.append("observacao", observacao.trim());
  }
  return apiRequestForm<OrcamentoAnexo>(`/orcamentos/${orcamentoId}/anexos`, {
    method: "POST",
    role,
    formData,
  });
}

export async function listOrcamentoAnexos(
  role: UserRole,
  orcamentoId: number
): Promise<PaginatedResponse<OrcamentoAnexo>> {
  return apiRequest<PaginatedResponse<OrcamentoAnexo>>(
    `/orcamentos/${orcamentoId}/anexos?page=1&page_size=100`,
    { role }
  );
}

export async function downloadOrcamentoAnexo(
  role: UserRole,
  anexoId: number
): Promise<{ blob: Blob; fileName: string }> {
  const response = await fetch(`${API_BASE_URL}/orcamentos/anexos/${anexoId}/download`, {
    method: "GET",
    headers: {
      "X-User-Role": role,
    },
  });
  if (!response.ok) {
    let detail = "Falha no download do anexo";
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

  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const fileNameMatch = /filename="?([^"]+)"?/.exec(contentDisposition);
  const fileName = fileNameMatch?.[1] ?? `anexo-${anexoId}`;
  return { blob, fileName };
}

export async function downloadOrcamentoPdf(
  role: UserRole,
  orcamentoId: number,
  versao?: number
): Promise<{ blob: Blob; fileName: string }> {
  const query = versao && versao > 0 ? `?versao=${versao}` : "";
  const response = await fetch(`${API_BASE_URL}/orcamentos/${orcamentoId}/pdf${query}`, {
    method: "GET",
    headers: {
      "X-User-Role": role,
    },
  });
  if (!response.ok) {
    let detail = "Falha no download do PDF do orcamento";
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

  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const fileNameMatch = /filename="?([^"]+)"?/.exec(contentDisposition);
  const fileName = fileNameMatch?.[1] ?? `orcamento-${orcamentoId}.pdf`;
  return { blob, fileName };
}

export { ApiError };
