"""Adiciona indices para consultas analiticas e rastreabilidade.

Revision ID: 20260216_0008
Revises: 20260216_0007
Create Date: 2026-02-16 23:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0008"
down_revision = "20260216_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ordens_data_emissao_status
        ON ordens_de_producao (data_emissao, status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ordens_operacoes_ordem_centro
        ON ordens_operacoes (ordem_id, centro_trabalho_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_estoque_mov_ordem_tipo_data
        ON estoque_movimentacoes (ordem_id, tipo_movimento, data_hora)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orcamentos_produto_status_created
        ON orcamentos (produto_final_id, status, created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_orcamentos_produto_status_created")
    op.execute("DROP INDEX IF EXISTS idx_estoque_mov_ordem_tipo_data")
    op.execute("DROP INDEX IF EXISTS idx_ordens_operacoes_ordem_centro")
    op.execute("DROP INDEX IF EXISTS idx_ordens_data_emissao_status")
