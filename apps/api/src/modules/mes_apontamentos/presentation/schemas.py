from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from modules.ordens_producao.presentation.schemas import OrdemOperacaoStatus, OrdemStatus
from shared.application.pagination import PageMeta


class EventoMES(StrEnum):
    START = "START"
    STOP = "STOP"
    PAUSA = "PAUSA"
    RETOMADA = "RETOMADA"


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class ApontamentoCreate(SchemaBase):
    evento: EventoMES
    data_hora_evento: datetime | None = None
    motivo: str | None = Field(default=None, max_length=200)
    quantidade_produzida: Decimal = Field(default=Decimal("0"), ge=0)


class ApontamentoResponse(SchemaBase):
    id: int
    ordem_operacao_id: int
    ordem_id: int
    evento: EventoMES
    data_hora_evento: datetime
    motivo: str | None
    quantidade_produzida: Decimal
    status_operacao: OrdemOperacaoStatus
    status_ordem: OrdemStatus
    created_at: datetime


class ApontamentoListResponse(SchemaBase):
    items: list[ApontamentoResponse]
    meta: PageMeta


class RefugoCreate(SchemaBase):
    quantidade: Decimal = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=200)
    data_hora: datetime | None = None


class RefugoResponse(SchemaBase):
    id: int
    ordem_operacao_id: int
    ordem_id: int
    quantidade: Decimal
    motivo: str
    data_hora: datetime
    quantidade_refugada_total_ordem: Decimal


class RefugoListResponse(SchemaBase):
    items: list[RefugoResponse]
    meta: PageMeta


class ResumoTempoResponse(SchemaBase):
    ordem_operacao_id: int
    ordem_id: int
    status_operacao: OrdemOperacaoStatus
    status_ordem: OrdemStatus
    quantidade_eventos: int
    ultimo_evento: EventoMES | None
    ultima_data_hora: datetime | None
    total_segundos: Decimal
    total_horas: Decimal
    quantidade_produzida_total: Decimal
    quantidade_refugada_total: Decimal
