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
