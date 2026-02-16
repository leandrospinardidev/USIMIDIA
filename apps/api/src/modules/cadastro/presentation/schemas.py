from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from shared.application.pagination import PageMeta


class UnidadeMedida(StrEnum):
    UN = "UN"
    KG = "KG"
    M = "M"
    M2 = "M2"
    M3 = "M3"
    L = "L"


class CategoriaInsumo(StrEnum):
    CHAPA = "CHAPA"
    PERFIL = "PERFIL"
    PARAFUSO = "PARAFUSO"
    ELETRONICO = "ELETRONICO"
    QUIMICO = "QUIMICO"
    OUTRO = "OUTRO"


class TipoMaquina(StrEnum):
    ROUTER_CNC = "ROUTER_CNC"
    LASER_CO2 = "LASER_CO2"
    TORNO_CNC = "TORNO_CNC"
    FRESA_CNC = "FRESA_CNC"
    MONTAGEM = "MONTAGEM"
    INSPECAO = "INSPECAO"


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class ClienteCreate(SchemaBase):
    codigo: str = Field(min_length=1, max_length=30)
    razao_social: str = Field(min_length=1, max_length=150)
    nome_fantasia: str | None = Field(default=None, max_length=150)
    cnpj_cpf: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    telefone: str | None = Field(default=None, max_length=30)
    ativo: bool = True


class ClienteUpdate(SchemaBase):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    razao_social: str | None = Field(default=None, min_length=1, max_length=150)
    nome_fantasia: str | None = Field(default=None, max_length=150)
    cnpj_cpf: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    telefone: str | None = Field(default=None, max_length=30)
    ativo: bool | None = None


class ClienteResponse(SchemaBase):
    id: int
    codigo: str
    razao_social: str
    nome_fantasia: str | None
    cnpj_cpf: str | None
    email: str | None
    telefone: str | None
    ativo: bool
    created_at: datetime
    updated_at: datetime


class InsumoCreate(SchemaBase):
    codigo: str = Field(min_length=1, max_length=30)
    descricao: str = Field(min_length=1, max_length=200)
    categoria: CategoriaInsumo
    unidade_medida: UnidadeMedida
    custo_unitario: Decimal = Field(default=Decimal("0"), ge=0)
    controla_lote: bool = True
    largura_mm: Decimal | None = Field(default=None, ge=0)
    altura_mm: Decimal | None = Field(default=None, ge=0)
    espessura_mm: Decimal | None = Field(default=None, ge=0)
    estoque_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    ativo: bool = True


class InsumoUpdate(SchemaBase):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    descricao: str | None = Field(default=None, min_length=1, max_length=200)
    categoria: CategoriaInsumo | None = None
    unidade_medida: UnidadeMedida | None = None
    custo_unitario: Decimal | None = Field(default=None, ge=0)
    controla_lote: bool | None = None
    largura_mm: Decimal | None = Field(default=None, ge=0)
    altura_mm: Decimal | None = Field(default=None, ge=0)
    espessura_mm: Decimal | None = Field(default=None, ge=0)
    estoque_minimo: Decimal | None = Field(default=None, ge=0)
    ativo: bool | None = None


class InsumoResponse(SchemaBase):
    id: int
    codigo: str
    descricao: str
    categoria: CategoriaInsumo
    unidade_medida: UnidadeMedida
    custo_unitario: Decimal
    controla_lote: bool
    largura_mm: Decimal | None
    altura_mm: Decimal | None
    espessura_mm: Decimal | None
    estoque_minimo: Decimal
    ativo: bool
    created_at: datetime
    updated_at: datetime


class CentroTrabalhoCreate(SchemaBase):
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=120)
    tipo_maquina: TipoMaquina
    taxa_horaria: Decimal = Field(ge=0)
    setup_padrao_min: int = Field(default=0, ge=0)
    capacidade_horas_dia: Decimal = Field(default=Decimal("8"), gt=0)
    ativo: bool = True


class CentroTrabalhoUpdate(SchemaBase):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    tipo_maquina: TipoMaquina | None = None
    taxa_horaria: Decimal | None = Field(default=None, ge=0)
    setup_padrao_min: int | None = Field(default=None, ge=0)
    capacidade_horas_dia: Decimal | None = Field(default=None, gt=0)
    ativo: bool | None = None


class CentroTrabalhoResponse(SchemaBase):
    id: int
    codigo: str
    nome: str
    tipo_maquina: TipoMaquina
    taxa_horaria: Decimal
    setup_padrao_min: int
    capacidade_horas_dia: Decimal
    ativo: bool
    created_at: datetime
    updated_at: datetime


class ProdutoFinalCreate(SchemaBase):
    codigo: str = Field(min_length=1, max_length=40)
    descricao: str = Field(min_length=1, max_length=200)
    revisao_atual: str = Field(default="A", min_length=1, max_length=10)
    unidade_medida: UnidadeMedida = UnidadeMedida.UN
    margem_lucro_padrao_pct: Decimal = Field(default=Decimal("30"), ge=0)
    ativo: bool = True


class ProdutoFinalUpdate(SchemaBase):
    codigo: str | None = Field(default=None, min_length=1, max_length=40)
    descricao: str | None = Field(default=None, min_length=1, max_length=200)
    revisao_atual: str | None = Field(default=None, min_length=1, max_length=10)
    unidade_medida: UnidadeMedida | None = None
    margem_lucro_padrao_pct: Decimal | None = Field(default=None, ge=0)
    ativo: bool | None = None


class ProdutoFinalResponse(SchemaBase):
    id: int
    codigo: str
    descricao: str
    revisao_atual: str
    unidade_medida: UnidadeMedida
    margem_lucro_padrao_pct: Decimal
    ativo: bool
    created_at: datetime
    updated_at: datetime


class ClienteListResponse(SchemaBase):
    items: list[ClienteResponse]
    meta: PageMeta


class InsumoListResponse(SchemaBase):
    items: list[InsumoResponse]
    meta: PageMeta


class CentroTrabalhoListResponse(SchemaBase):
    items: list[CentroTrabalhoResponse]
    meta: PageMeta


class ProdutoFinalListResponse(SchemaBase):
    items: list[ProdutoFinalResponse]
    meta: PageMeta
