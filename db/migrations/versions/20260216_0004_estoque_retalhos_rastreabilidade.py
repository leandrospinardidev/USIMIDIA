"""Adiciona rastreabilidade de retalho por lote de origem.

Revision ID: 20260216_0004
Revises: 20260216_0003
Create Date: 2026-02-16 16:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0004"
down_revision = "20260216_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE estoque_lotes
        ADD COLUMN IF NOT EXISTS is_retalho BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE estoque_lotes
        ADD COLUMN IF NOT EXISTS lote_origem_id BIGINT REFERENCES estoque_lotes(id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_estoque_lotes_insumo_saldo
        ON estoque_lotes (insumo_id, quantidade_disponivel)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_estoque_lotes_origem
        ON estoque_lotes (lote_origem_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_estoque_lotes_origem")
    op.execute("DROP INDEX IF EXISTS idx_estoque_lotes_insumo_saldo")
    op.execute("ALTER TABLE estoque_lotes DROP COLUMN IF EXISTS lote_origem_id")
    op.execute("ALTER TABLE estoque_lotes DROP COLUMN IF EXISTS is_retalho")
