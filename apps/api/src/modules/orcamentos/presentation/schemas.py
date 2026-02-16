from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from shared.application.pagination import PageMeta


class OrcamentoStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    ENVIADO = "ENVIADO"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class OrcamentoOperacaoInput(SchemaBase):
    centro_trabalho_id: int = Field(gt=0)
    setup_min: Decimal | None = Field(default=None, ge=0)
    ciclo_min: Decimal = Field(default=Decimal("0"), ge=0)
    descricao: str | None = Field(default=None, max_length=200)


class OrcamentoCalculoRequest(SchemaBase):
    cliente_id: int | None = Field(default=None, gt=0)
    produto_final_id: int = Field(gt=0)
    bom_id: int | None = Field(default=None, gt=0)
    preset_cnc_id: int | None = Field(default=None, gt=0)
    quantidade: Decimal = Field(gt=0)
    margem_lucro_pct: Decimal | None = Field(default=None, ge=0)
    custo_indireto_fixo: Decimal = Field(default=Decimal("0"), ge=0)
    custo_indireto_pct: Decimal = Field(default=Decimal("0"), ge=0)
    operacoes: list[OrcamentoOperacaoInput] = Field(default_factory=list)


class OrcamentoCreate(OrcamentoCalculoRequest):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    referencia_projeto: str | None = Field(default=None, max_length=80)
    observacao: str | None = Field(default=None, max_length=3000)
    moeda: str = Field(default="BRL", min_length=3, max_length=10)


class OrcamentoVersaoCreate(SchemaBase):
    bom_id: int | None = Field(default=None, gt=0)
    preset_cnc_id: int | None = Field(default=None, gt=0)
    quantidade: Decimal = Field(gt=0)
    margem_lucro_pct: Decimal | None = Field(default=None, ge=0)
    custo_indireto_fixo: Decimal = Field(default=Decimal("0"), ge=0)
    custo_indireto_pct: Decimal = Field(default=Decimal("0"), ge=0)
    operacoes: list[OrcamentoOperacaoInput] = Field(default_factory=list)
    referencia_projeto: str | None = Field(default=None, max_length=80)
    observacao: str | None = Field(default=None, max_length=3000)
    moeda: str = Field(default="BRL", min_length=3, max_length=10)


class OrcamentoOperacaoResultado(SchemaBase):
    sequencia: int
    centro_trabalho_id: int
    codigo_centro: str
    nome_centro: str
    setup_min: Decimal
    ciclo_min: Decimal
    tempo_total_horas: Decimal
    taxa_horaria: Decimal
    custo_operacao: Decimal
    descricao: str | None


class OrcamentoMaterialResultado(SchemaBase):
    insumo_id: int
    codigo: str
    descricao: str
    unidade_medida: str
    quantidade_total: Decimal
    custo_unitario: Decimal
    custo_total: Decimal


class OrcamentoSimulacaoResponse(SchemaBase):
    produto_final_id: int
    bom_id: int
    quantidade: Decimal
    margem_lucro_pct: Decimal
    custo_material_total: Decimal
    custo_maquina_total: Decimal
    custo_indireto_total: Decimal
    custo_total: Decimal
    preco_venda: Decimal
    materiais: list[OrcamentoMaterialResultado]
    operacoes: list[OrcamentoOperacaoResultado]


class OrcamentoPdfLeituraResumo(SchemaBase):
    material_inferido: str | None
    quantidade_inferida: int | None
    quantidade_considerada: int
    diametros_mm: list[Decimal]
    comprimento_mm: Decimal | None
    confianca: str
    texto_resumo: str


class OrcamentoPdfCustosResumo(SchemaBase):
    centro_trabalho_id: int
    centro_codigo: str
    centro_nome: str
    taxa_horaria: Decimal
    horas_maquina_estimadas_unit: Decimal
    custo_material_unitario: Decimal
    custo_material_total: Decimal
    custo_maquina_total: Decimal
    custo_indireto_total: Decimal
    custo_total: Decimal
    margem_lucro_pct: Decimal
    preco_venda_sugerido: Decimal


class OrcamentoPdfSimulacaoResponse(SchemaBase):
    leitura: OrcamentoPdfLeituraResumo
    custos: OrcamentoPdfCustosResumo
    premissas: list[str]


class OrcamentoPresetOperacaoTemplate(SchemaBase):
    sequencia: int = Field(ge=1, le=9999)
    centro_trabalho_id: int | None = Field(default=None, gt=0)
    setup_min: Decimal = Field(default=Decimal("0"), ge=0)
    ciclo_min: Decimal = Field(default=Decimal("0"), ge=0)
    descricao: str | None = Field(default=None, max_length=200)


class OrcamentoPresetCncCreate(SchemaBase):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = Field(default=None, max_length=3000)
    ativo: bool = True
    cliente_id: int | None = Field(default=None, gt=0)
    produto_final_id: int | None = Field(default=None, gt=0)
    centro_trabalho_id: int | None = Field(default=None, gt=0)
    fabricante_referencia: str | None = Field(default=None, max_length=80)
    linha_maquina_referencia: str | None = Field(default=None, max_length=80)
    perfil_maquina: str | None = Field(default=None, max_length=80)
    familia_peca: str | None = Field(default=None, max_length=80)
    tipo_peca: str | None = Field(default=None, max_length=20)
    material_referencia: str | None = Field(default=None, max_length=80)
    operacao_principal: str | None = Field(default=None, max_length=80)
    diametro_referencia_mm: Decimal | None = Field(default=None, ge=0)
    comprimento_referencia_mm: Decimal | None = Field(default=None, ge=0)
    fator_ciclo: Decimal = Field(default=Decimal("1"), gt=0)
    fator_setup: Decimal = Field(default=Decimal("1"), gt=0)
    margem_lucro_pct: Decimal = Field(default=Decimal("25"), ge=0)
    custo_indireto_pct: Decimal = Field(default=Decimal("6"), ge=0)
    operacoes_template: list[OrcamentoPresetOperacaoTemplate] = Field(default_factory=list)
    heuristicas: dict = Field(default_factory=dict)
    motivo_versao: str | None = Field(default=None, max_length=300)


class OrcamentoPresetCncUpdate(SchemaBase):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = Field(default=None, max_length=3000)
    ativo: bool | None = None
    cliente_id: int | None = Field(default=None, gt=0)
    produto_final_id: int | None = Field(default=None, gt=0)
    centro_trabalho_id: int | None = Field(default=None, gt=0)
    fabricante_referencia: str | None = Field(default=None, max_length=80)
    linha_maquina_referencia: str | None = Field(default=None, max_length=80)
    perfil_maquina: str | None = Field(default=None, max_length=80)
    familia_peca: str | None = Field(default=None, max_length=80)
    tipo_peca: str | None = Field(default=None, max_length=20)
    material_referencia: str | None = Field(default=None, max_length=80)
    operacao_principal: str | None = Field(default=None, max_length=80)
    diametro_referencia_mm: Decimal | None = Field(default=None, ge=0)
    comprimento_referencia_mm: Decimal | None = Field(default=None, ge=0)
    fator_ciclo: Decimal | None = Field(default=None, gt=0)
    fator_setup: Decimal | None = Field(default=None, gt=0)
    margem_lucro_pct: Decimal | None = Field(default=None, ge=0)
    custo_indireto_pct: Decimal | None = Field(default=None, ge=0)
    operacoes_template: list[OrcamentoPresetOperacaoTemplate] | None = None
    heuristicas: dict | None = None
    motivo_versao: str | None = Field(default=None, max_length=300)


class OrcamentoPresetRecalibrarRequest(SchemaBase):
    janela_dias: int = Field(default=90, ge=1, le=3650)
    centro_trabalho_id: int | None = Field(default=None, gt=0)
    produto_final_id: int | None = Field(default=None, gt=0)
    suavizacao_alpha: Decimal = Field(default=Decimal("0.65"), ge=0, le=1)
    motivo_versao: str | None = Field(default=None, max_length=300)


class OrcamentoPresetRecalibrarResponse(SchemaBase):
    preset_id: int
    preset_nome: str
    janela_dias: int
    amostras_utilizadas: int
    fator_ciclo_anterior: Decimal
    fator_ciclo_novo: Decimal
    fator_setup_anterior: Decimal
    fator_setup_novo: Decimal
    tempo_planejado_min_total: Decimal
    tempo_real_min_total: Decimal
    desvio_medio_pct: Decimal
    ultima_calibracao_at: datetime


class OrcamentoPresetCncResponse(SchemaBase):
    id: int
    versao_atual: int
    codigo: str
    nome: str
    descricao: str | None
    ativo: bool
    cliente_id: int | None
    produto_final_id: int | None
    centro_trabalho_id: int | None
    fabricante_referencia: str | None
    linha_maquina_referencia: str | None
    perfil_maquina: str | None
    familia_peca: str | None
    tipo_peca: str | None
    material_referencia: str | None
    operacao_principal: str | None
    diametro_referencia_mm: Decimal | None
    comprimento_referencia_mm: Decimal | None
    fator_ciclo: Decimal
    fator_setup: Decimal
    margem_lucro_pct: Decimal
    custo_indireto_pct: Decimal
    operacoes_template: list[OrcamentoPresetOperacaoTemplate]
    heuristicas: dict
    amostras_mes: int
    total_aplicacoes: int
    total_orcamentos: int
    erro_absoluto_acumulado_pct: Decimal
    tempo_planejado_min_total: Decimal
    tempo_real_min_total: Decimal
    ultima_calibracao_at: datetime | None
    ultima_aplicacao_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrcamentoPresetCncListResponse(SchemaBase):
    items: list[OrcamentoPresetCncResponse]
    meta: PageMeta


class OrcamentoPresetHistoricoItem(SchemaBase):
    id: int
    preset_id: int
    versao: int
    acao: str
    motivo: str | None
    snapshot: dict
    metricas: dict
    created_at: datetime


class OrcamentoPresetHistoricoListResponse(SchemaBase):
    items: list[OrcamentoPresetHistoricoItem]
    meta: PageMeta


class OrcamentoPresetRegistrarUsoRequest(SchemaBase):
    tipo_evento: str = Field(default="APLICACAO_MANUAL", min_length=1, max_length=40)
    erro_previsao_pct: Decimal | None = Field(default=None, ge=0)
    observacao: str | None = Field(default=None, max_length=300)


class OrcamentoPresetRegistrarUsoResponse(SchemaBase):
    preset_id: int
    versao_atual: int
    total_aplicacoes: int
    total_orcamentos: int
    erro_absoluto_acumulado_pct: Decimal
    ultima_aplicacao_at: datetime | None


class OrcamentoPresetRankingItem(SchemaBase):
    preset: OrcamentoPresetCncResponse
    score_uso: Decimal
    score_assertividade: Decimal
    score_contexto: Decimal
    score_final: Decimal
    motivos: list[str]


class OrcamentoPresetRankingResponse(SchemaBase):
    items: list[OrcamentoPresetRankingItem]


class OrcamentoPresetSugestaoResponse(SchemaBase):
    preset: OrcamentoPresetCncResponse | None
    score_final: Decimal | None
    motivos: list[str]


class OrcamentoVersaoResponse(SchemaBase):
    id: int
    versao: int
    bom_id: int
    quantidade: Decimal
    margem_lucro_pct: Decimal
    custo_material_total: Decimal
    custo_maquina_total: Decimal
    custo_indireto_total: Decimal
    preco_venda: Decimal
    moeda: str
    created_at: datetime
    materiais: list[OrcamentoMaterialResultado]
    operacoes: list[OrcamentoOperacaoResultado]


class OrcamentoAnexoResponse(SchemaBase):
    id: int
    orcamento_id: int
    nome_arquivo_original: str
    content_type: str | None
    tamanho_bytes: int
    observacao: str | None
    uploaded_at: datetime
    download_path: str


class OrcamentoAnexoListResponse(SchemaBase):
    items: list[OrcamentoAnexoResponse]
    meta: PageMeta


class OrcamentoResponse(SchemaBase):
    id: int
    codigo: str
    status: OrcamentoStatus
    cliente_id: int | None
    cliente_nome: str | None
    produto_final_id: int
    produto_codigo: str
    produto_descricao: str
    referencia_projeto: str | None
    observacao: str | None
    created_at: datetime
    updated_at: datetime
    versoes: list[OrcamentoVersaoResponse]
    anexos: list[OrcamentoAnexoResponse]


class OrcamentoListItem(SchemaBase):
    id: int
    codigo: str
    status: OrcamentoStatus
    cliente_id: int | None
    cliente_nome: str | None
    produto_final_id: int
    produto_codigo: str
    produto_descricao: str
    referencia_projeto: str | None
    versao_atual: int | None
    preco_venda_atual: Decimal | None
    created_at: datetime
    updated_at: datetime


class OrcamentoListResponse(SchemaBase):
    items: list[OrcamentoListItem]
    meta: PageMeta


class OrcamentoStatusUpdate(SchemaBase):
    status: OrcamentoStatus
