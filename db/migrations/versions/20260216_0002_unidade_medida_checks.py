"""Adiciona checks de unidade de medida para cadastros.

Revision ID: 20260216_0002
Revises: 20260216_0001
Create Date: 2026-02-16 12:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0002"
down_revision = "20260216_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE insumos
        ADD CONSTRAINT ck_insumos_unidade_medida
        CHECK (unidade_medida IN ('UN','KG','M','M2','M3','L'))
        """
    )
    op.execute(
        """
        ALTER TABLE produtos_finais
        ADD CONSTRAINT ck_produtos_finais_unidade_medida
        CHECK (unidade_medida IN ('UN','KG','M','M2','M3','L'))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE produtos_finais DROP CONSTRAINT IF EXISTS ck_produtos_finais_unidade_medida")
    op.execute("ALTER TABLE insumos DROP CONSTRAINT IF EXISTS ck_insumos_unidade_medida")
