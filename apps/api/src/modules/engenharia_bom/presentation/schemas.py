from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from modules.cadastro.presentation.schemas import UnidadeMedida
from shared.application.pagination import PageMeta


class BomStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    ATIVA = "ATIVA"
    OBSOLETA = "OBSOLETA"


class BomItemTipo(StrEnum):
    INSUMO = "INSUMO"
    SUBCONJUNTO = "SUBCONJUNTO"


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class BomCreate(SchemaBase):
    produto_final_id: int = Field(gt=0)
    status: BomStatus = BomStatus.RASCUNHO
    valido_de: date | None = None
    valido_ate: date | None = None
    observacao: str | None = Field(default=None, max_length=3000)


class BomUpdate(SchemaBase):
    status: BomStatus | None = None
    valido_de: date | None = None
    valido_ate: date | None = None
    observacao: str | None = Field(default=None, max_length=3000)


class BomResponse(SchemaBase):
    id: int
    produto_final_id: int
    versao: int
    status: BomStatus
    valido_de: date
    valido_ate: date | None
    observacao: str | None
    created_at: datetime
    updated_at: datetime


class BomListResponse(SchemaBase):
    items: list[BomResponse]
    meta: PageMeta


class BomItemCreate(SchemaBase):
    parent_item_id: int | None = Field(default=None, gt=0)
    ordem: int = Field(default=1, ge=1, le=9999)
    item_tipo: BomItemTipo
    insumo_id: int | None = Field(default=None, gt=0)
    produto_filho_id: int | None = Field(default=None, gt=0)
    quantidade: Decimal = Field(gt=0)
    unidade_medida: UnidadeMedida | None = None
    perda_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    observacao: str | None = Field(default=None, max_length=3000)


class BomItemUpdate(SchemaBase):
    parent_item_id: int | None = Field(default=None, gt=0)
    ordem: int | None = Field(default=None, ge=1, le=9999)
    item_tipo: BomItemTipo | None = None
    insumo_id: int | None = Field(default=None, gt=0)
    produto_filho_id: int | None = Field(default=None, gt=0)
    quantidade: Decimal | None = Field(default=None, gt=0)
    unidade_medida: UnidadeMedida | None = None
    perda_pct: Decimal | None = Field(default=None, ge=0, le=100)
    observacao: str | None = Field(default=None, max_length=3000)


class BomItemResponse(SchemaBase):
    id: int
    bom_id: int
    parent_item_id: int | None
    ordem: int
    item_tipo: BomItemTipo
    insumo_id: int | None
    produto_filho_id: int | None
    quantidade: Decimal
    unidade_medida: UnidadeMedida
    perda_pct: Decimal
    observacao: str | None
    created_at: datetime
    updated_at: datetime


class BomTreeNode(SchemaBase):
    id: int
    parent_item_id: int | None
    ordem: int
    item_tipo: BomItemTipo
    insumo_id: int | None
    produto_filho_id: int | None
    codigo: str | None
    descricao: str | None
    quantidade: Decimal
    unidade_medida: UnidadeMedida
    perda_pct: Decimal
    observacao: str | None
    children: list[BomTreeNode] = Field(default_factory=list)


BomTreeNode.model_rebuild()


class BomTreeResponse(SchemaBase):
    bom: BomResponse
    tree: list[BomTreeNode]


class BomExplosionInsumo(SchemaBase):
    insumo_id: int
    codigo: str
    descricao: str
    unidade_medida: UnidadeMedida
    quantidade_total: Decimal
    custo_unitario: Decimal
    custo_total: Decimal


class BomExplosionResponse(SchemaBase):
    bom_id: int
    produto_final_id: int
    quantidade_base: Decimal
    insumos: list[BomExplosionInsumo]
    custo_total_materiais: Decimal
