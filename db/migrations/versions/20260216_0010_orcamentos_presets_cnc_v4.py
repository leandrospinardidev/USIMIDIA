"""Adiciona presets CNC persistidos para orcamentos (V4).

Revision ID: 20260216_0010
Revises: 20260216_0009
Create Date: 2026-02-16 22:50:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0010"
down_revision = "20260216_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orcamento_presets_cnc (
            id BIGSERIAL PRIMARY KEY,
            codigo VARCHAR(40) NOT NULL UNIQUE,
            nome VARCHAR(120) NOT NULL,
            descricao TEXT,
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            cliente_id BIGINT REFERENCES clientes(id),
            produto_final_id BIGINT REFERENCES produtos_finais(id),
            centro_trabalho_id BIGINT REFERENCES centros_de_trabalho(id),
            fabricante_referencia VARCHAR(80),
            linha_maquina_referencia VARCHAR(80),
            perfil_maquina VARCHAR(80),
            familia_peca VARCHAR(80),
            tipo_peca VARCHAR(20),
            material_referencia VARCHAR(80),
            operacao_principal VARCHAR(80),
            diametro_referencia_mm NUMERIC(10,3),
            comprimento_referencia_mm NUMERIC(10,3),
            fator_ciclo NUMERIC(10,4) NOT NULL DEFAULT 1 CHECK (fator_ciclo > 0),
            fator_setup NUMERIC(10,4) NOT NULL DEFAULT 1 CHECK (fator_setup > 0),
            margem_lucro_pct NUMERIC(6,2) NOT NULL DEFAULT 25 CHECK (margem_lucro_pct >= 0),
            custo_indireto_pct NUMERIC(6,2) NOT NULL DEFAULT 6 CHECK (custo_indireto_pct >= 0),
            operacoes_template_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            heuristicas_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            amostras_mes INTEGER NOT NULL DEFAULT 0 CHECK (amostras_mes >= 0),
            tempo_planejado_min_total NUMERIC(14,2) NOT NULL DEFAULT 0
                CHECK (tempo_planejado_min_total >= 0),
            tempo_real_min_total NUMERIC(14,2) NOT NULL DEFAULT 0
                CHECK (tempo_real_min_total >= 0),
            ultima_calibracao_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_orc_preset_diametro_ref
                CHECK (diametro_referencia_mm IS NULL OR diametro_referencia_mm >= 0),
            CONSTRAINT ck_orc_preset_comprimento_ref
                CHECK (comprimento_referencia_mm IS NULL OR comprimento_referencia_mm >= 0)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_orc_preset_scope
        ON orcamento_presets_cnc (
            ativo,
            cliente_id,
            produto_final_id,
            updated_at DESC
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_orc_preset_scope")
    op.execute("DROP TABLE IF EXISTS orcamento_presets_cnc")
