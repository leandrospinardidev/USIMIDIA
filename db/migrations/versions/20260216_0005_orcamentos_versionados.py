"""Cria estrutura de orcamentos versionados com operacoes.

Revision ID: 20260216_0005
Revises: 20260216_0004
Create Date: 2026-02-16 18:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0005"
down_revision = "20260216_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orcamentos (
            id BIGSERIAL PRIMARY KEY,
            codigo VARCHAR(40) NOT NULL UNIQUE,
            cliente_id BIGINT REFERENCES clientes(id),
            produto_final_id BIGINT NOT NULL REFERENCES produtos_finais(id),
            status VARCHAR(20) NOT NULL DEFAULT 'RASCUNHO'
                CHECK (status IN ('RASCUNHO','ENVIADO','APROVADO','REJEITADO')),
            observacao TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orcamento_versoes (
            id BIGSERIAL PRIMARY KEY,
            orcamento_id BIGINT NOT NULL REFERENCES orcamentos(id) ON DELETE CASCADE,
            versao INTEGER NOT NULL,
            bom_id BIGINT NOT NULL REFERENCES bom(id),
            quantidade NUMERIC(14,4) NOT NULL CHECK (quantidade > 0),
            margem_lucro_pct NUMERIC(6,2) NOT NULL CHECK (margem_lucro_pct >= 0),
            custo_material_total NUMERIC(14,4) NOT NULL CHECK (custo_material_total >= 0),
            custo_maquina_total NUMERIC(14,4) NOT NULL CHECK (custo_maquina_total >= 0),
            custo_indireto_total NUMERIC(14,4) NOT NULL CHECK (custo_indireto_total >= 0),
            preco_venda NUMERIC(14,4) NOT NULL CHECK (preco_venda >= 0),
            moeda VARCHAR(10) NOT NULL DEFAULT 'BRL',
            detalhes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (orcamento_id, versao)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orcamento_versao_operacoes (
            id BIGSERIAL PRIMARY KEY,
            orcamento_versao_id BIGINT NOT NULL REFERENCES orcamento_versoes(id) ON DELETE CASCADE,
            sequencia SMALLINT NOT NULL,
            centro_trabalho_id BIGINT NOT NULL REFERENCES centros_de_trabalho(id),
            setup_min NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (setup_min >= 0),
            ciclo_min NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (ciclo_min >= 0),
            tempo_total_horas NUMERIC(14,4) NOT NULL CHECK (tempo_total_horas >= 0),
            taxa_horaria NUMERIC(12,2) NOT NULL CHECK (taxa_horaria >= 0),
            custo_operacao NUMERIC(14,4) NOT NULL CHECK (custo_operacao >= 0),
            descricao VARCHAR(200),
            UNIQUE (orcamento_versao_id, sequencia)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orcamentos_produto_status
        ON orcamentos (produto_final_id, status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orcamentos_cliente
        ON orcamentos (cliente_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orc_versoes_orcamento_versao
        ON orcamento_versoes (orcamento_id, versao DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orc_versao_ops_versao
        ON orcamento_versao_operacoes (orcamento_versao_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_orc_versao_ops_versao")
    op.execute("DROP INDEX IF EXISTS idx_orc_versoes_orcamento_versao")
    op.execute("DROP INDEX IF EXISTS idx_orcamentos_cliente")
    op.execute("DROP INDEX IF EXISTS idx_orcamentos_produto_status")
    op.execute("DROP TABLE IF EXISTS orcamento_versao_operacoes")
    op.execute("DROP TABLE IF EXISTS orcamento_versoes")
    op.execute("DROP TABLE IF EXISTS orcamentos")
