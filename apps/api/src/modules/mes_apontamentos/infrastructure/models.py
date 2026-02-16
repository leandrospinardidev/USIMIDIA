from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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


class ApontamentoProducaoModel(Base):
    __tablename__ = "apontamentos_producao"
    __table_args__ = (
        CheckConstraint(
            "evento IN ('START','STOP','PAUSA','RETOMADA')",
            name="ck_apontamentos_evento",
        ),
        CheckConstraint(
            "quantidade_produzida >= 0",
            name="ck_apontamentos_qtd_produzida",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    ordem_operacao_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("ordens_operacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    evento: Mapped[str] = mapped_column(String(20), nullable=False)
    data_hora_evento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    motivo: Mapped[str | None] = mapped_column(String(200))
    quantidade_produzida: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RefugoProducaoModel(Base):
    __tablename__ = "refugos_producao"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_refugos_quantidade"),
    )

    id: Mapped[int] = _bigint_pk()
    ordem_operacao_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("ordens_operacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    motivo: Mapped[str] = mapped_column(String(200), nullable=False)
    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
