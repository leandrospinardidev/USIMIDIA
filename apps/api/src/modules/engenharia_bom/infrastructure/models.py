from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
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


class BomModel(Base):
    __tablename__ = "bom"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RASCUNHO','ATIVA','OBSOLETA')",
            name="ck_bom_status",
        ),
        UniqueConstraint("produto_final_id", "versao", name="uq_bom_produto_versao"),
    )

    id: Mapped[int] = _bigint_pk()
    produto_final_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("produtos_finais.id"),
        nullable=False,
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    valido_de: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    valido_ate: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BomItemModel(Base):
    __tablename__ = "bom_itens"
    __table_args__ = (
        CheckConstraint(
            "item_tipo IN ('INSUMO','SUBCONJUNTO')",
            name="ck_bom_itens_tipo",
        ),
        CheckConstraint(
            "perda_pct >= 0 AND perda_pct <= 100",
            name="ck_bom_itens_perda_pct",
        ),
        CheckConstraint(
            "quantidade > 0",
            name="ck_bom_itens_quantidade",
        ),
        CheckConstraint(
            "("
            "(item_tipo = 'INSUMO' AND insumo_id IS NOT NULL AND produto_filho_id IS NULL)"
            " OR "
            "(item_tipo = 'SUBCONJUNTO' AND produto_filho_id IS NOT NULL AND insumo_id IS NULL)"
            ")",
            name="ck_bom_itens_relacao_tipo",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    bom_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("bom.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_item_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("bom_itens.id", ondelete="CASCADE"),
    )
    ordem: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    item_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    insumo_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("insumos.id"),
    )
    produto_filho_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("produtos_finais.id"),
    )
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unidade_medida: Mapped[str] = mapped_column(String(10), nullable=False)
    perda_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
