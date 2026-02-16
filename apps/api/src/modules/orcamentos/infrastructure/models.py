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

JsonType = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _bigint_pk():
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class OrcamentoModel(Base):
    __tablename__ = "orcamentos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RASCUNHO','ENVIADO','APROVADO','REJEITADO')",
            name="ck_orcamentos_status",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    cliente_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("clientes.id"),
    )
    produto_final_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("produtos_finais.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="RASCUNHO",
        server_default="RASCUNHO",
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


class OrcamentoVersaoModel(Base):
    __tablename__ = "orcamento_versoes"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_orc_versoes_quantidade"),
        CheckConstraint(
            "margem_lucro_pct >= 0",
            name="ck_orc_versoes_margem",
        ),
        CheckConstraint(
            "custo_material_total >= 0",
            name="ck_orc_versoes_custo_material",
        ),
        CheckConstraint(
            "custo_maquina_total >= 0",
            name="ck_orc_versoes_custo_maquina",
        ),
        CheckConstraint(
            "custo_indireto_total >= 0",
            name="ck_orc_versoes_custo_indireto",
        ),
        CheckConstraint("preco_venda >= 0", name="ck_orc_versoes_preco"),
        UniqueConstraint("orcamento_id", "versao", name="uq_orcamento_versao"),
    )

    id: Mapped[int] = _bigint_pk()
    orcamento_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("orcamentos.id", ondelete="CASCADE"),
        nullable=False,
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    bom_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("bom.id"),
        nullable=False,
    )
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    margem_lucro_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    custo_material_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    custo_maquina_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    custo_indireto_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    moeda: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL", server_default="BRL")
    detalhes_json: Mapped[dict] = mapped_column(
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


class OrcamentoVersaoOperacaoModel(Base):
    __tablename__ = "orcamento_versao_operacoes"
    __table_args__ = (
        CheckConstraint("setup_min >= 0", name="ck_orc_op_setup"),
        CheckConstraint("ciclo_min >= 0", name="ck_orc_op_ciclo"),
        CheckConstraint("tempo_total_horas >= 0", name="ck_orc_op_tempo"),
        CheckConstraint("taxa_horaria >= 0", name="ck_orc_op_taxa"),
        CheckConstraint("custo_operacao >= 0", name="ck_orc_op_custo"),
        UniqueConstraint("orcamento_versao_id", "sequencia", name="uq_orc_versao_op_seq"),
    )

    id: Mapped[int] = _bigint_pk()
    orcamento_versao_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("orcamento_versoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequencia: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    centro_trabalho_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("centros_de_trabalho.id"),
        nullable=False,
    )
    setup_min: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    ciclo_min: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    tempo_total_horas: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    taxa_horaria: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    custo_operacao: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(200))
