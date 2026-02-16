"""Adiciona referencia de projeto e anexos em orcamentos.

Revision ID: 20260216_0009
Revises: 20260216_0008
Create Date: 2026-02-16 20:30:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0009"
down_revision = "20260216_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE orcamentos
        ADD COLUMN IF NOT EXISTS referencia_projeto VARCHAR(80)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orcamento_anexos (
            id BIGSERIAL PRIMARY KEY,
            orcamento_id BIGINT NOT NULL REFERENCES orcamentos(id) ON DELETE CASCADE,
            nome_arquivo_original VARCHAR(255) NOT NULL,
            nome_arquivo_storage VARCHAR(255) NOT NULL UNIQUE,
            content_type VARCHAR(120),
            tamanho_bytes BIGINT NOT NULL CHECK (tamanho_bytes >= 0),
            caminho_relativo VARCHAR(500) NOT NULL,
            observacao VARCHAR(300),
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orcamento_anexos_orcamento
        ON orcamento_anexos (orcamento_id, uploaded_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_orcamento_anexos_orcamento")
    op.execute("DROP TABLE IF EXISTS orcamento_anexos")
    op.execute("ALTER TABLE orcamentos DROP COLUMN IF EXISTS referencia_projeto")
