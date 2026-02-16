"""Adiciona snapshot JSON da BOM em ordens de producao.

Revision ID: 20260216_0006
Revises: 20260216_0005
Create Date: 2026-02-16 20:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0006"
down_revision = "20260216_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE ordens_de_producao
        ADD COLUMN IF NOT EXISTS bom_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ordens_bom_snapshot_gin
        ON ordens_de_producao USING GIN (bom_snapshot_json)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ordens_bom_snapshot_gin")
    op.execute("ALTER TABLE ordens_de_producao DROP COLUMN IF EXISTS bom_snapshot_json")
