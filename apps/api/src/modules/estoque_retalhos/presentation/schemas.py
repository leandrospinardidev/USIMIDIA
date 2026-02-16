from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from modules.cadastro.presentation.schemas import UnidadeMedida
from shared.application.pagination import PageMeta


class MovimentoTipo(StrEnum):
    ENTRADA = "ENTRADA"
    CONSUMO_OP = "CONSUMO_OP"
    AJUSTE = "AJUSTE"
    RETALHO_GERADO = "RETALHO_GERADO"
    RETALHO_CONSUMIDO = "RETALHO_CONSUMIDO"


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class LoteEntradaCreate(SchemaBase):
    insumo_id: int = Field(gt=0)
    codigo_lote: str = Field(min_length=1, max_length=40)
    quantidade_inicial: Decimal = Field(gt=0)
    largura_mm: Decimal | None = Field(default=None, ge=0)
    altura_mm: Decimal | None = Field(default=None, ge=0)
    espessura_mm: Decimal | None = Field(default=None, ge=0)
    custo_total: Decimal = Field(default=Decimal("0"), ge=0)
    ordem_id: int | None = Field(default=None, gt=0)
    observacao: str | None = Field(default=None, max_length=200)


class LoteResponse(SchemaBase):
    id: int
    insumo_id: int
    insumo_codigo: str
    insumo_descricao: str
    unidade_medida: UnidadeMedida
    codigo_lote: str
    quantidade_inicial: Decimal
    quantidade_disponivel: Decimal
    largura_mm: Decimal | None
    altura_mm: Decimal | None
    espessura_mm: Decimal | None
    custo_total: Decimal
    is_retalho: bool
    lote_origem_id: int | None
    criado_em: datetime


class LoteListResponse(SchemaBase):
    items: list[LoteResponse]
    meta: PageMeta


class LoteConsumoCreate(SchemaBase):
    quantidade: Decimal = Field(gt=0)
    ordem_id: int | None = Field(default=None, gt=0)
    tipo_movimento: MovimentoTipo | None = None
    largura_mm: Decimal | None = Field(default=None, ge=0)
    altura_mm: Decimal | None = Field(default=None, ge=0)
    observacao: str | None = Field(default=None, max_length=200)


class GerarRetalhoCreate(SchemaBase):
    codigo_lote_retalho: str = Field(min_length=1, max_length=40)
    quantidade: Decimal = Field(gt=0)
    ordem_id: int | None = Field(default=None, gt=0)
    largura_mm: Decimal | None = Field(default=None, ge=0)
    altura_mm: Decimal | None = Field(default=None, ge=0)
    observacao: str | None = Field(default=None, max_length=200)


class GerarRetalhoResponse(SchemaBase):
    lote_origem: LoteResponse
    lote_retalho: LoteResponse


class AjusteLoteCreate(SchemaBase):
    delta_quantidade: Decimal
    ordem_id: int | None = Field(default=None, gt=0)
    largura_mm: Decimal | None = Field(default=None, ge=0)
    altura_mm: Decimal | None = Field(default=None, ge=0)
    observacao: str | None = Field(default=None, max_length=200)


class MovimentacaoResponse(SchemaBase):
    id: int
    lote_id: int
    ordem_id: int | None
    tipo_movimento: MovimentoTipo
    quantidade: Decimal
    largura_mm: Decimal | None
    altura_mm: Decimal | None
    data_hora: datetime
    observacao: str | None


class MovimentacaoListResponse(SchemaBase):
    items: list[MovimentacaoResponse]
    meta: PageMeta


class SaldoInsumoResponse(SchemaBase):
    insumo_id: int
    codigo: str
    descricao: str
    unidade_medida: UnidadeMedida
    saldo_disponivel: Decimal
    lotes_com_saldo: int
