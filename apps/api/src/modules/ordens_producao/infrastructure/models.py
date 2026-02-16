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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from core.database import Base

JsonType = JSON().with_variant(JSONB, "postgresql")


def _bigint_pk():
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class OrdemProducaoModel(Base):
    __tablename__ = "ordens_de_producao"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ABERTA','PLANEJADA','EM_PRODUCAO','PAUSADA','FINALIZADA','CANCELADA')",
            name="ck_ordens_status",
        ),
        CheckConstraint(
            "quantidade_planejada > 0",
            name="ck_ordens_quantidade_planejada",
        ),
        CheckConstraint(
            "quantidade_produzida >= 0",
            name="ck_ordens_quantidade_produzida",
        ),
        CheckConstraint(
            "quantidade_refugada >= 0",
            name="ck_ordens_quantidade_refugada",
        ),
        CheckConstraint("prioridade BETWEEN 1 AND 5", name="ck_ordens_prioridade"),
    )

    id: Mapped[int] = _bigint_pk()
    numero_op: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    cliente_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("clientes.id"),
    )
    produto_final_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("produtos_finais.id"),
        nullable=False,
    )
    bom_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("bom.id"),
        nullable=False,
    )
    centro_trabalho_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("centros_de_trabalho.id"),
    )
    quantidade_planejada: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantidade_produzida: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    quantidade_refugada: Mapped[Decimal] = mapped_column(
        Numeric(14, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ABERTA",
        server_default="ABERTA",
    )
    prioridade: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=3,
        server_default="3",
    )
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    previsao_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    previsao_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inicio_real: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim_real: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observacao: Mapped[str | None] = mapped_column(Text)
    bom_snapshot_json: Mapped[dict] = mapped_column(
        JsonType,
        nullable=False,
        default=dict,
        server_default="{}",
    )
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


class OrdemOperacaoModel(Base):
    __tablename__ = "ordens_operacoes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDENTE','EM_EXECUCAO','PAUSADA','CONCLUIDA')",
            name="ck_ordens_operacoes_status",
        ),
        CheckConstraint("setup_planejado_min >= 0", name="ck_ordens_operacoes_setup"),
        CheckConstraint("ciclo_planejado_min >= 0", name="ck_ordens_operacoes_ciclo"),
        UniqueConstraint("ordem_id", "sequencia", name="uq_ordens_operacoes_seq"),
    )

    id: Mapped[int] = _bigint_pk()
    ordem_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("ordens_de_producao.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequencia: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    centro_trabalho_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("centros_de_trabalho.id"),
        nullable=False,
    )
    setup_planejado_min: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    ciclo_planejado_min: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDENTE",
        server_default="PENDENTE",
    )
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
