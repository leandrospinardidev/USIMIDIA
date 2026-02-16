from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from shared.application.pagination import PageMeta


class OrdemStatus(StrEnum):
    ABERTA = "ABERTA"
    PLANEJADA = "PLANEJADA"
    EM_PRODUCAO = "EM_PRODUCAO"
    PAUSADA = "PAUSADA"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


class OrdemOperacaoStatus(StrEnum):
    PENDENTE = "PENDENTE"
    EM_EXECUCAO = "EM_EXECUCAO"
    PAUSADA = "PAUSADA"
    CONCLUIDA = "CONCLUIDA"


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class OrdemOperacaoCreate(SchemaBase):
    sequencia: int | None = Field(default=None, ge=1, le=9999)
    centro_trabalho_id: int = Field(gt=0)
    setup_planejado_min: Decimal | None = Field(default=None, ge=0)
    ciclo_planejado_min: Decimal = Field(default=Decimal("0"), ge=0)
    status: OrdemOperacaoStatus = OrdemOperacaoStatus.PENDENTE


class OrdemProducaoCreate(SchemaBase):
    numero_op: str | None = Field(default=None, min_length=1, max_length=30)
    cliente_id: int | None = Field(default=None, gt=0)
    produto_final_id: int = Field(gt=0)
    bom_id: int | None = Field(default=None, gt=0)
    centro_trabalho_id: int | None = Field(default=None, gt=0)
    quantidade_planejada: Decimal = Field(gt=0)
    prioridade: int = Field(default=3, ge=1, le=5)
    previsao_inicio: datetime | None = None
    previsao_fim: datetime | None = None
    observacao: str | None = Field(default=None, max_length=3000)
    operacoes: list[OrdemOperacaoCreate] = Field(default_factory=list)


class OrdemStatusUpdate(SchemaBase):
    status: OrdemStatus


class OrdemOperacaoResponse(SchemaBase):
    id: int
    sequencia: int
    centro_trabalho_id: int
    centro_codigo: str
    centro_nome: str
    setup_planejado_min: Decimal
    ciclo_planejado_min: Decimal
    status: OrdemOperacaoStatus
    created_at: datetime
    updated_at: datetime


class OrdemListItem(SchemaBase):
    id: int
    numero_op: str
    status: OrdemStatus
    cliente_id: int | None
    cliente_nome: str | None
    produto_final_id: int
    produto_codigo: str
    produto_descricao: str
    bom_id: int
    quantidade_planejada: Decimal
    quantidade_produzida: Decimal
    quantidade_refugada: Decimal
    prioridade: int
    data_emissao: date
    previsao_inicio: datetime | None
    previsao_fim: datetime | None
    created_at: datetime
    updated_at: datetime


class OrdemListResponse(SchemaBase):
    items: list[OrdemListItem]
    meta: PageMeta


class OrdemProducaoResponse(SchemaBase):
    id: int
    numero_op: str
    status: OrdemStatus
    cliente_id: int | None
    cliente_nome: str | None
    produto_final_id: int
    produto_codigo: str
    produto_descricao: str
    bom_id: int
    quantidade_planejada: Decimal
    quantidade_produzida: Decimal
    quantidade_refugada: Decimal
    prioridade: int
    data_emissao: date
    previsao_inicio: datetime | None
    previsao_fim: datetime | None
    inicio_real: datetime | None
    fim_real: datetime | None
    observacao: str | None
    bom_snapshot_json: dict
    created_at: datetime
    updated_at: datetime
    operacoes: list[OrdemOperacaoResponse]
