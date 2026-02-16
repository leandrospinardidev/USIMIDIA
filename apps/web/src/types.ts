export type UserRole = "admin" | "pcp" | "operador" | "compras";

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PageMeta;
}

export interface OrdemListItem {
  id: number;
  numero_op: string;
  status: string;
  cliente_nome: string | null;
  produto_codigo: string;
  produto_descricao: string;
  quantidade_planejada: string;
  quantidade_produzida: string;
  quantidade_refugada: string;
  prioridade: number;
}

export interface OrdemOperacao {
  id: number;
  sequencia: number;
  centro_trabalho_id: number;
  centro_codigo: string;
  centro_nome: string;
  setup_planejado_min: string;
  ciclo_planejado_min: string;
  status: "PENDENTE" | "EM_EXECUCAO" | "PAUSADA" | "CONCLUIDA";
}

export interface OrdemDetail extends OrdemListItem {
  cliente_id: number | null;
  produto_final_id: number;
  bom_id: number;
  data_emissao: string;
  previsao_inicio: string | null;
  previsao_fim: string | null;
  inicio_real: string | null;
  fim_real: string | null;
  observacao: string | null;
  operacoes: OrdemOperacao[];
}

export type EventoMES = "START" | "PAUSA" | "RETOMADA" | "STOP";

export interface Apontamento {
  id: number;
  ordem_operacao_id: number;
  ordem_id: number;
  evento: EventoMES;
  data_hora_evento: string;
  motivo: string | null;
  quantidade_produzida: string;
  status_operacao: OrdemOperacao["status"];
  status_ordem: string;
  created_at: string;
}

export interface Refugo {
  id: number;
  ordem_operacao_id: number;
  ordem_id: number;
  quantidade: string;
  motivo: string;
  data_hora: string;
  quantidade_refugada_total_ordem: string;
}

export interface ResumoTempo {
  ordem_operacao_id: number;
  ordem_id: number;
  status_operacao: OrdemOperacao["status"];
  status_ordem: string;
  quantidade_eventos: number;
  ultimo_evento: EventoMES | null;
  ultima_data_hora: string | null;
  total_segundos: string;
  total_horas: string;
  quantidade_produzida_total: string;
  quantidade_refugada_total: string;
}

export interface KpisGerais {
  periodo_inicio: string | null;
  periodo_fim: string | null;
  total_ordens: number;
  quantidade_planejada_total: string;
  quantidade_produzida_total: string;
  quantidade_refugada_total: string;
  refugo_pct: string;
  tempo_planejado_horas: string;
  tempo_real_horas: string;
  eficiencia_pct: string;
  custo_material_planejado: string;
  custo_material_real: string;
  custo_maquina_planejado: string;
  custo_maquina_real: string;
  custo_total_planejado: string;
  custo_total_real: string;
  custo_total_orcado: string | null;
  desvio_custo_real_vs_orcado: string | null;
}

export interface IndicadorOrdemItem {
  ordem_id: number;
  numero_op: string;
  status: string;
  data_emissao: string;
  produto_codigo: string;
  produto_descricao: string;
  cliente_nome: string | null;
  quantidade_planejada: string;
  quantidade_produzida: string;
  quantidade_refugada: string;
  refugo_pct: string;
  tempo_planejado_horas: string;
  tempo_real_horas: string;
  eficiencia_pct: string;
  custo_material_planejado: string;
  custo_material_real: string;
  custo_maquina_planejado: string;
  custo_maquina_real: string;
  custo_total_planejado: string;
  custo_total_real: string;
  custo_total_orcado: string | null;
  desvio_custo_real_vs_orcado: string | null;
}

export interface RastreabilidadeOperacaoResumo {
  ordem_operacao_id: number;
  sequencia: number;
  centro_codigo: string;
  centro_nome: string;
  status: string;
  quantidade_eventos: number;
  quantidade_refugos: number;
  tempo_real_horas: string;
}

export interface RastreabilidadeMovimentacao {
  id: number;
  lote_id: number;
  codigo_lote: string;
  insumo_id: number;
  insumo_codigo: string;
  insumo_descricao: string;
  tipo_movimento: string;
  quantidade: string;
  custo_aproximado: string;
  ordem_id: number | null;
  data_hora: string;
  observacao: string | null;
  is_retalho: boolean;
  lote_origem_id: number | null;
}

export interface RastreabilidadeLote {
  lote_id: number;
  codigo_lote: string;
  insumo_id: number;
  insumo_codigo: string;
  insumo_descricao: string;
  quantidade_inicial: string;
  quantidade_disponivel: string;
  custo_total: string;
  is_retalho: boolean;
  lote_origem_id: number | null;
}

export interface RastreabilidadeFluxoRetalho {
  lote_origem_id: number;
  lote_retalho_id: number;
}

export interface RastreabilidadeOrdem {
  ordem_id: number;
  numero_op: string;
  status: string;
  data_emissao: string;
  produto_codigo: string;
  produto_descricao: string;
  cliente_nome: string | null;
  quantidade_planejada: string;
  quantidade_produzida: string;
  quantidade_refugada: string;
  bom_snapshot_json: Record<string, unknown>;
  operacoes: RastreabilidadeOperacaoResumo[];
  movimentacoes: RastreabilidadeMovimentacao[];
  lotes_relacionados: RastreabilidadeLote[];
  fluxo_retalhos: RastreabilidadeFluxoRetalho[];
}
