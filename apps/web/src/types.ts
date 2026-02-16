export type UserRole = "admin" | "pcp" | "operador" | "compras";
export type TipoMaquina =
  | "ROUTER_CNC"
  | "LASER_CO2"
  | "TORNO_CNC"
  | "FRESA_CNC"
  | "MONTAGEM"
  | "INSPECAO";

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

export type OrcamentoStatus = "RASCUNHO" | "ENVIADO" | "APROVADO" | "REJEITADO";

export interface ClienteCadastro {
  id: number;
  codigo: string;
  razao_social: string;
}

export interface ProdutoFinalCadastro {
  id: number;
  codigo: string;
  descricao: string;
  margem_lucro_padrao_pct: string;
}

export interface CentroTrabalhoCadastro {
  id: number;
  codigo: string;
  nome: string;
  tipo_maquina: TipoMaquina;
  taxa_horaria: string;
  setup_padrao_min: number;
  capacidade_horas_dia: string;
}

export interface BomListItem {
  id: number;
  produto_final_id: number;
  versao: number;
  status: string;
}

export interface OrcamentoOperacaoInput {
  centro_trabalho_id: number;
  setup_min?: string;
  ciclo_min: string;
  descricao?: string;
}

export interface OrcamentoMaterialResultado {
  insumo_id: number;
  codigo: string;
  descricao: string;
  unidade_medida: string;
  quantidade_total: string;
  custo_unitario: string;
  custo_total: string;
}

export interface OrcamentoOperacaoResultado {
  sequencia: number;
  centro_trabalho_id: number;
  codigo_centro: string;
  nome_centro: string;
  setup_min: string;
  ciclo_min: string;
  tempo_total_horas: string;
  taxa_horaria: string;
  custo_operacao: string;
  descricao: string | null;
}

export interface OrcamentoSimulacao {
  produto_final_id: number;
  bom_id: number;
  quantidade: string;
  margem_lucro_pct: string;
  custo_material_total: string;
  custo_maquina_total: string;
  custo_indireto_total: string;
  custo_total: string;
  preco_venda: string;
  materiais: OrcamentoMaterialResultado[];
  operacoes: OrcamentoOperacaoResultado[];
}

export interface OrcamentoPdfLeitura {
  material_inferido: string | null;
  quantidade_inferida: number | null;
  quantidade_considerada: number;
  diametros_mm: string[];
  comprimento_mm: string | null;
  confianca: "BAIXA" | "MEDIA" | "ALTA" | string;
  texto_resumo: string;
}

export interface OrcamentoPdfCustos {
  centro_trabalho_id: number;
  centro_codigo: string;
  centro_nome: string;
  taxa_horaria: string;
  horas_maquina_estimadas_unit: string;
  custo_material_unitario: string;
  custo_material_total: string;
  custo_maquina_total: string;
  custo_indireto_total: string;
  custo_total: string;
  margem_lucro_pct: string;
  preco_venda_sugerido: string;
}

export interface OrcamentoPdfSimulacao {
  leitura: OrcamentoPdfLeitura;
  custos: OrcamentoPdfCustos;
  premissas: string[];
}

export interface OrcamentoPresetOperacaoTemplate {
  sequencia: number;
  centro_trabalho_id: number | null;
  setup_min: string;
  ciclo_min: string;
  descricao: string | null;
}

export interface OrcamentoPresetCnc {
  id: number;
  versao_atual: number;
  codigo: string;
  nome: string;
  descricao: string | null;
  ativo: boolean;
  cliente_id: number | null;
  produto_final_id: number | null;
  centro_trabalho_id: number | null;
  fabricante_referencia: string | null;
  linha_maquina_referencia: string | null;
  perfil_maquina: string | null;
  familia_peca: string | null;
  tipo_peca: string | null;
  material_referencia: string | null;
  operacao_principal: string | null;
  diametro_referencia_mm: string | null;
  comprimento_referencia_mm: string | null;
  fator_ciclo: string;
  fator_setup: string;
  margem_lucro_pct: string;
  custo_indireto_pct: string;
  operacoes_template: OrcamentoPresetOperacaoTemplate[];
  heuristicas: Record<string, unknown>;
  amostras_mes: number;
  total_aplicacoes: number;
  total_orcamentos: number;
  erro_absoluto_acumulado_pct: string;
  tempo_planejado_min_total: string;
  tempo_real_min_total: string;
  ultima_calibracao_at: string | null;
  ultima_aplicacao_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrcamentoPresetRecalibracao {
  preset_id: number;
  preset_nome: string;
  janela_dias: number;
  amostras_utilizadas: number;
  fator_ciclo_anterior: string;
  fator_ciclo_novo: string;
  fator_setup_anterior: string;
  fator_setup_novo: string;
  tempo_planejado_min_total: string;
  tempo_real_min_total: string;
  desvio_medio_pct: string;
  ultima_calibracao_at: string;
}

export interface OrcamentoPresetHistoricoItem {
  id: number;
  preset_id: number;
  versao: number;
  acao: "CRIACAO" | "ATUALIZACAO" | "RECALIBRACAO" | string;
  motivo: string | null;
  snapshot: Record<string, unknown>;
  metricas: Record<string, unknown>;
  created_at: string;
}

export interface OrcamentoPresetRegistroUso {
  preset_id: number;
  versao_atual: number;
  total_aplicacoes: number;
  total_orcamentos: number;
  erro_absoluto_acumulado_pct: string;
  ultima_aplicacao_at: string | null;
}

export interface OrcamentoPresetRankingItem {
  preset: OrcamentoPresetCnc;
  score_uso: string;
  score_assertividade: string;
  score_contexto: string;
  score_final: string;
  motivos: string[];
}

export interface OrcamentoPresetSugestao {
  preset: OrcamentoPresetCnc | null;
  score_final: string | null;
  motivos: string[];
}

export interface OrcamentoAnexo {
  id: number;
  orcamento_id: number;
  nome_arquivo_original: string;
  content_type: string | null;
  tamanho_bytes: number;
  observacao: string | null;
  uploaded_at: string;
  download_path: string;
}

export interface OrcamentoVersao {
  id: number;
  versao: number;
  bom_id: number;
  quantidade: string;
  margem_lucro_pct: string;
  custo_material_total: string;
  custo_maquina_total: string;
  custo_indireto_total: string;
  preco_venda: string;
  moeda: string;
  created_at: string;
  materiais: OrcamentoMaterialResultado[];
  operacoes: OrcamentoOperacaoResultado[];
}

export interface OrcamentoListItem {
  id: number;
  codigo: string;
  status: OrcamentoStatus;
  cliente_id: number | null;
  cliente_nome: string | null;
  produto_final_id: number;
  produto_codigo: string;
  produto_descricao: string;
  referencia_projeto: string | null;
  versao_atual: number | null;
  preco_venda_atual: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrcamentoDetail {
  id: number;
  codigo: string;
  status: OrcamentoStatus;
  cliente_id: number | null;
  cliente_nome: string | null;
  produto_final_id: number;
  produto_codigo: string;
  produto_descricao: string;
  referencia_projeto: string | null;
  observacao: string | null;
  created_at: string;
  updated_at: string;
  versoes: OrcamentoVersao[];
  anexos: OrcamentoAnexo[];
}
