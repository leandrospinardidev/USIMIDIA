from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _bigint_pk():
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class ClienteModel(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = _bigint_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    razao_social: Mapped[str] = mapped_column(String(150), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(150))
    cnpj_cpf: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(150))
    telefone: Mapped[str | None] = mapped_column(String(30))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class InsumoModel(Base):
    __tablename__ = "insumos"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('CHAPA','PERFIL','PARAFUSO','ELETRONICO','QUIMICO','OUTRO')",
            name="ck_insumos_categoria",
        ),
        CheckConstraint(
            "unidade_medida IN ('UN','KG','M','M2','M3','L')",
            name="ck_insumos_unidade_medida",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    unidade_medida: Mapped[str] = mapped_column(String(10), nullable=False)
    custo_unitario: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    controla_lote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    largura_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    altura_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    espessura_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    estoque_minimo: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CentroTrabalhoModel(Base):
    __tablename__ = "centros_de_trabalho"
    __table_args__ = (
        CheckConstraint(
            "tipo_maquina IN ('ROUTER_CNC','LASER_CO2','TORNO_CNC','FRESA_CNC','MONTAGEM','INSPECAO')",
            name="ck_centros_tipo_maquina",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo_maquina: Mapped[str] = mapped_column(String(30), nullable=False)
    taxa_horaria: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    setup_padrao_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    capacidade_horas_dia: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("8"), server_default="8"
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProdutoFinalModel(Base):
    __tablename__ = "produtos_finais"
    __table_args__ = (
        CheckConstraint(
            "unidade_medida IN ('UN','KG','M','M2','M3','L')",
            name="ck_produtos_finais_unidade_medida",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    revisao_atual: Mapped[str] = mapped_column(String(10), nullable=False, default="A", server_default="A")
    unidade_medida: Mapped[str] = mapped_column(String(10), nullable=False, default="UN", server_default="UN")
    margem_lucro_padrao_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("30"), server_default="30"
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
