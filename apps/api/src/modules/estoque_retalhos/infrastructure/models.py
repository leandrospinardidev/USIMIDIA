from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _bigint_pk():
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class EstoqueLoteModel(Base):
    __tablename__ = "estoque_lotes"
    __table_args__ = (
        CheckConstraint(
            "quantidade_inicial > 0",
            name="ck_estoque_lotes_quantidade_inicial",
        ),
        CheckConstraint(
            "quantidade_disponivel >= 0",
            name="ck_estoque_lotes_quantidade_disponivel",
        ),
        CheckConstraint("custo_total >= 0", name="ck_estoque_lotes_custo_total"),
    )

    id: Mapped[int] = _bigint_pk()
    insumo_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("insumos.id"),
        nullable=False,
    )
    codigo_lote: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    quantidade_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_disponivel: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    largura_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    altura_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    espessura_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    custo_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    is_retalho: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    lote_origem_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("estoque_lotes.id"),
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EstoqueMovimentacaoModel(Base):
    __tablename__ = "estoque_movimentacoes"
    __table_args__ = (
        CheckConstraint(
            "tipo_movimento IN "
            "('ENTRADA','CONSUMO_OP','AJUSTE','RETALHO_GERADO','RETALHO_CONSUMIDO')",
            name="ck_estoque_mov_tipo",
        ),
        CheckConstraint("quantidade > 0", name="ck_estoque_mov_quantidade"),
    )

    id: Mapped[int] = _bigint_pk()
    lote_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("estoque_lotes.id"),
        nullable=False,
    )
    ordem_id: Mapped[int | None] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    tipo_movimento: Mapped[str] = mapped_column(String(30), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    largura_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    altura_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    observacao: Mapped[str | None] = mapped_column(String(200))
