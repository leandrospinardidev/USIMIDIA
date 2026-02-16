from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from modules.ordens_producao.presentation.schemas import OrdemStatus
from shared.application.pagination import PageMeta


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class KpisGeraisResponse(SchemaBase):
    periodo_inicio: date | None
    periodo_fim: date | None
    total_ordens: int
    quantidade_planejada_total: Decimal
    quantidade_produzida_total: Decimal
    quantidade_refugada_total: Decimal
    refugo_pct: Decimal
    tempo_planejado_horas: Decimal
    tempo_real_horas: Decimal
    eficiencia_pct: Decimal
    custo_material_planejado: Decimal
    custo_material_real: Decimal
    custo_maquina_planejado: Decimal
    custo_maquina_real: Decimal
    custo_total_planejado: Decimal
    custo_total_real: Decimal
    custo_total_orcado: Decimal | None
    desvio_custo_real_vs_orcado: Decimal | None


class IndicadorOrdemItem(SchemaBase):
    ordem_id: int
    numero_op: str
    status: OrdemStatus
    data_emissao: date
    produto_codigo: str
    produto_descricao: str
    cliente_nome: str | None
    quantidade_planejada: Decimal
    quantidade_produzida: Decimal
    quantidade_refugada: Decimal
    refugo_pct: Decimal
    tempo_planejado_horas: Decimal
    tempo_real_horas: Decimal
    eficiencia_pct: Decimal
    custo_material_planejado: Decimal
    custo_material_real: Decimal
    custo_maquina_planejado: Decimal
    custo_maquina_real: Decimal
    custo_total_planejado: Decimal
    custo_total_real: Decimal
    custo_total_orcado: Decimal | None
    desvio_custo_real_vs_orcado: Decimal | None


class IndicadoresOrdemListResponse(SchemaBase):
    items: list[IndicadorOrdemItem]
    meta: PageMeta


class RastreabilidadeMovimentacao(SchemaBase):
    id: int
    lote_id: int
    codigo_lote: str
    insumo_id: int
    insumo_codigo: str
    insumo_descricao: str
    tipo_movimento: str
    quantidade: Decimal
    custo_aproximado: Decimal
    ordem_id: int | None
    data_hora: datetime
    observacao: str | None
    is_retalho: bool
    lote_origem_id: int | None


class RastreabilidadeLote(SchemaBase):
    lote_id: int
    codigo_lote: str
    insumo_id: int
    insumo_codigo: str
    insumo_descricao: str
    quantidade_inicial: Decimal
    quantidade_disponivel: Decimal
    custo_total: Decimal
    is_retalho: bool
    lote_origem_id: int | None


class RastreabilidadeFluxoRetalho(SchemaBase):
    lote_origem_id: int
    lote_retalho_id: int


class RastreabilidadeOperacaoResumo(SchemaBase):
    ordem_operacao_id: int
    sequencia: int
    centro_codigo: str
    centro_nome: str
    status: str
    quantidade_eventos: int
    quantidade_refugos: int
    tempo_real_horas: Decimal


class RastreabilidadeOrdemResponse(SchemaBase):
    ordem_id: int
    numero_op: str
    status: OrdemStatus
    data_emissao: date
    produto_codigo: str
    produto_descricao: str
    cliente_nome: str | None
    quantidade_planejada: Decimal
    quantidade_produzida: Decimal
    quantidade_refugada: Decimal
    bom_snapshot_json: dict
    operacoes: list[RastreabilidadeOperacaoResumo]
    movimentacoes: list[RastreabilidadeMovimentacao]
    lotes_relacionados: list[RastreabilidadeLote]
    fluxo_retalhos: list[RastreabilidadeFluxoRetalho]
