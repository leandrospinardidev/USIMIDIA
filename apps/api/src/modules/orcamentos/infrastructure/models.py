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
    referencia_projeto: Mapped[str | None] = mapped_column(String(80))
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
    moeda: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="BRL",
        server_default="BRL",
    )
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


class OrcamentoAnexoModel(Base):
    __tablename__ = "orcamento_anexos"
    __table_args__ = (
        CheckConstraint("tamanho_bytes >= 0", name="ck_orc_anexo_tamanho"),
    )

    id: Mapped[int] = _bigint_pk()
    orcamento_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("orcamentos.id", ondelete="CASCADE"),
        nullable=False,
    )
    nome_arquivo_original: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_arquivo_storage: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str | None] = mapped_column(String(120))
    tamanho_bytes: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    caminho_relativo: Mapped[str] = mapped_column(String(500), nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(300))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class OrcamentoPresetCncModel(Base):
    __tablename__ = "orcamento_presets_cnc"
    __table_args__ = (
        CheckConstraint("fator_ciclo > 0", name="ck_orc_preset_fator_ciclo"),
        CheckConstraint("fator_setup > 0", name="ck_orc_preset_fator_setup"),
        CheckConstraint(
            "margem_lucro_pct >= 0",
            name="ck_orc_preset_margem_lucro",
        ),
        CheckConstraint(
            "custo_indireto_pct >= 0",
            name="ck_orc_preset_custo_indireto",
        ),
        CheckConstraint(
            "diametro_referencia_mm IS NULL OR diametro_referencia_mm >= 0",
            name="ck_orc_preset_diametro_ref",
        ),
        CheckConstraint(
            "comprimento_referencia_mm IS NULL OR comprimento_referencia_mm >= 0",
            name="ck_orc_preset_comprimento_ref",
        ),
        CheckConstraint(
            "amostras_mes >= 0",
            name="ck_orc_preset_amostras_mes",
        ),
        CheckConstraint(
            "tempo_planejado_min_total >= 0",
            name="ck_orc_preset_tempo_planejado",
        ),
        CheckConstraint(
            "tempo_real_min_total >= 0",
            name="ck_orc_preset_tempo_real",
        ),
        CheckConstraint(
            "versao_atual >= 1",
            name="ck_orc_preset_versao_atual",
        ),
        CheckConstraint(
            "total_aplicacoes >= 0",
            name="ck_orc_preset_total_aplicacoes",
        ),
        CheckConstraint(
            "total_orcamentos >= 0",
            name="ck_orc_preset_total_orcamentos",
        ),
        CheckConstraint(
            "erro_absoluto_acumulado_pct >= 0",
            name="ck_orc_preset_erro_abs_acumulado",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    versao_atual: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    codigo: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    cliente_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("clientes.id"),
    )
    produto_final_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("produtos_finais.id"),
    )
    centro_trabalho_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("centros_de_trabalho.id"),
    )
    fabricante_referencia: Mapped[str | None] = mapped_column(String(80))
    linha_maquina_referencia: Mapped[str | None] = mapped_column(String(80))
    perfil_maquina: Mapped[str | None] = mapped_column(String(80))
    familia_peca: Mapped[str | None] = mapped_column(String(80))
    tipo_peca: Mapped[str | None] = mapped_column(String(20))
    material_referencia: Mapped[str | None] = mapped_column(String(80))
    operacao_principal: Mapped[str | None] = mapped_column(String(80))
    diametro_referencia_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    comprimento_referencia_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    fator_ciclo: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("1"),
        server_default="1",
    )
    fator_setup: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        default=Decimal("1"),
        server_default="1",
    )
    margem_lucro_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("25"),
        server_default="25",
    )
    custo_indireto_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("6"),
        server_default="6",
    )
    operacoes_template_json: Mapped[list] = mapped_column(
        JsonType,
        nullable=False,
        default=list,
        server_default="[]",
    )
    heuristicas_json: Mapped[dict] = mapped_column(
        JsonType,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    amostras_mes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_aplicacoes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    total_orcamentos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    erro_absoluto_acumulado_pct: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    tempo_planejado_min_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    tempo_real_min_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    ultima_calibracao_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_aplicacao_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class OrcamentoPresetCncHistoricoModel(Base):
    __tablename__ = "orcamento_presets_cnc_historico"
    __table_args__ = (
        CheckConstraint("versao >= 1", name="ck_orc_preset_hist_versao"),
        CheckConstraint(
            "acao IN ('CRIACAO','ATUALIZACAO','RECALIBRACAO')",
            name="ck_orc_preset_hist_acao",
        ),
        UniqueConstraint(
            "preset_id",
            "versao",
            name="uq_orc_preset_hist_versao",
        ),
    )

    id: Mapped[int] = _bigint_pk()
    preset_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("orcamento_presets_cnc.id", ondelete="CASCADE"),
        nullable=False,
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(300))
    snapshot_json: Mapped[dict] = mapped_column(
        JsonType,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    metricas_json: Mapped[dict] = mapped_column(
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
