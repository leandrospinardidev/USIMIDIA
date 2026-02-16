"""Adiciona quantidade produzida por evento de apontamento MES.

Revision ID: 20260216_0007
Revises: 20260216_0006
Create Date: 2026-02-16 22:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0007"
down_revision = "20260216_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE apontamentos_producao
        ADD COLUMN IF NOT EXISTS quantidade_produzida NUMERIC(14,3) NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE apontamentos_producao
        ADD CONSTRAINT ck_apontamentos_quantidade_produzida
        CHECK (quantidade_produzida >= 0)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_refugos_operacao_data
        ON refugos_producao (ordem_operacao_id, data_hora)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_refugos_operacao_data")
    op.execute(
        "ALTER TABLE apontamentos_producao DROP CONSTRAINT IF EXISTS ck_apontamentos_quantidade_produzida"
    )
    op.execute("ALTER TABLE apontamentos_producao DROP COLUMN IF EXISTS quantidade_produzida")
