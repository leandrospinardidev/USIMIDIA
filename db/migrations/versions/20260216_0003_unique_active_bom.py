"""Garante somente uma BOM ativa por produto.

Revision ID: 20260216_0003
Revises: 20260216_0002
Create Date: 2026-02-16 14:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0003"
down_revision = "20260216_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bom_produto_status_ativa
        ON bom (produto_final_id)
        WHERE status = 'ATIVA'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_bom_produto_status_ativa")
