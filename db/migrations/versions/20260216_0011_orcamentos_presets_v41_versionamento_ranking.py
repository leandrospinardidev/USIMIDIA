"""V4.1: versionamento e ranking de presets CNC.

Revision ID: 20260216_0011
Revises: 20260216_0010
Create Date: 2026-02-16 23:40:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0011"
down_revision = "20260216_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE orcamento_presets_cnc
        ADD COLUMN IF NOT EXISTS versao_atual INTEGER NOT NULL DEFAULT 1
        """
    )
    op.execute(
        """
        ALTER TABLE orcamento_presets_cnc
        ADD COLUMN IF NOT EXISTS total_aplicacoes INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE orcamento_presets_cnc
        ADD COLUMN IF NOT EXISTS total_orcamentos INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE orcamento_presets_cnc
        ADD COLUMN IF NOT EXISTS erro_absoluto_acumulado_pct NUMERIC(14,4) NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE orcamento_presets_cnc
        ADD COLUMN IF NOT EXISTS ultima_aplicacao_at TIMESTAMPTZ
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orcamento_presets_cnc_historico (
            id BIGSERIAL PRIMARY KEY,
            preset_id BIGINT NOT NULL REFERENCES orcamento_presets_cnc(id) ON DELETE CASCADE,
            versao INTEGER NOT NULL CHECK (versao >= 1),
            acao VARCHAR(20) NOT NULL
                CHECK (acao IN ('CRIACAO','ATUALIZACAO','RECALIBRACAO')),
            motivo VARCHAR(300),
            snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metricas_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_orc_preset_hist_versao UNIQUE (preset_id, versao)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orc_preset_hist_preset
        ON orcamento_presets_cnc_historico (preset_id, versao DESC, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orc_preset_ranking
        ON orcamento_presets_cnc (
            ativo,
            cliente_id,
            produto_final_id,
            total_aplicacoes DESC,
            updated_at DESC
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_orc_preset_ranking")
    op.execute("DROP INDEX IF EXISTS idx_orc_preset_hist_preset")
    op.execute("DROP TABLE IF EXISTS orcamento_presets_cnc_historico")
    op.execute("ALTER TABLE orcamento_presets_cnc DROP COLUMN IF EXISTS ultima_aplicacao_at")
    op.execute("ALTER TABLE orcamento_presets_cnc DROP COLUMN IF EXISTS erro_absoluto_acumulado_pct")
    op.execute("ALTER TABLE orcamento_presets_cnc DROP COLUMN IF EXISTS total_orcamentos")
    op.execute("ALTER TABLE orcamento_presets_cnc DROP COLUMN IF EXISTS total_aplicacoes")
    op.execute("ALTER TABLE orcamento_presets_cnc DROP COLUMN IF EXISTS versao_atual")
