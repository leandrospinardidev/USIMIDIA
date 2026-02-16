"""Cria schema inicial do ERP industrial.

Revision ID: 20260216_0001
Revises:
Create Date: 2026-02-16 10:00:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE clientes (
            id BIGSERIAL PRIMARY KEY,
            codigo VARCHAR(30) NOT NULL UNIQUE,
            razao_social VARCHAR(150) NOT NULL,
            nome_fantasia VARCHAR(150),
            cnpj_cpf VARCHAR(20) UNIQUE,
            email VARCHAR(150),
            telefone VARCHAR(30),
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE insumos (
            id BIGSERIAL PRIMARY KEY,
            codigo VARCHAR(30) NOT NULL UNIQUE,
            descricao VARCHAR(200) NOT NULL,
            categoria VARCHAR(30) NOT NULL
                CHECK (categoria IN ('CHAPA','PERFIL','PARAFUSO','ELETRONICO','QUIMICO','OUTRO')),
            unidade_medida VARCHAR(10) NOT NULL,
            custo_unitario NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (custo_unitario >= 0),
            controla_lote BOOLEAN NOT NULL DEFAULT TRUE,
            largura_mm NUMERIC(10,2),
            altura_mm NUMERIC(10,2),
            espessura_mm NUMERIC(8,3),
            estoque_minimo NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE centros_de_trabalho (
            id BIGSERIAL PRIMARY KEY,
            codigo VARCHAR(30) NOT NULL UNIQUE,
            nome VARCHAR(120) NOT NULL,
            tipo_maquina VARCHAR(30) NOT NULL
                CHECK (tipo_maquina IN ('ROUTER_CNC','LASER_CO2','TORNO_CNC','FRESA_CNC','MONTAGEM','INSPECAO')),
            taxa_horaria NUMERIC(12,2) NOT NULL CHECK (taxa_horaria >= 0),
            setup_padrao_min INTEGER NOT NULL DEFAULT 0 CHECK (setup_padrao_min >= 0),
            capacidade_horas_dia NUMERIC(6,2) NOT NULL DEFAULT 8 CHECK (capacidade_horas_dia > 0),
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE produtos_finais (
            id BIGSERIAL PRIMARY KEY,
            codigo VARCHAR(40) NOT NULL UNIQUE,
            descricao VARCHAR(200) NOT NULL,
            revisao_atual VARCHAR(10) NOT NULL DEFAULT 'A',
            unidade_medida VARCHAR(10) NOT NULL DEFAULT 'UN',
            margem_lucro_padrao_pct NUMERIC(6,2) NOT NULL DEFAULT 30 CHECK (margem_lucro_padrao_pct >= 0),
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE bom (
            id BIGSERIAL PRIMARY KEY,
            produto_final_id BIGINT NOT NULL REFERENCES produtos_finais(id),
            versao INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL CHECK (status IN ('RASCUNHO','ATIVA','OBSOLETA')),
            valido_de DATE NOT NULL DEFAULT CURRENT_DATE,
            valido_ate DATE,
            observacao TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (produto_final_id, versao)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE bom_itens (
            id BIGSERIAL PRIMARY KEY,
            bom_id BIGINT NOT NULL REFERENCES bom(id) ON DELETE CASCADE,
            parent_item_id BIGINT REFERENCES bom_itens(id) ON DELETE CASCADE,
            ordem SMALLINT NOT NULL DEFAULT 1,
            item_tipo VARCHAR(20) NOT NULL CHECK (item_tipo IN ('INSUMO','SUBCONJUNTO')),
            insumo_id BIGINT REFERENCES insumos(id),
            produto_filho_id BIGINT REFERENCES produtos_finais(id),
            quantidade NUMERIC(14,4) NOT NULL CHECK (quantidade > 0),
            unidade_medida VARCHAR(10) NOT NULL,
            perda_pct NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (perda_pct >= 0 AND perda_pct <= 100),
            observacao TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (
                (item_tipo = 'INSUMO' AND insumo_id IS NOT NULL AND produto_filho_id IS NULL)
                OR
                (item_tipo = 'SUBCONJUNTO' AND produto_filho_id IS NOT NULL AND insumo_id IS NULL)
            )
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ordens_de_producao (
            id BIGSERIAL PRIMARY KEY,
            numero_op VARCHAR(30) NOT NULL UNIQUE,
            cliente_id BIGINT REFERENCES clientes(id),
            produto_final_id BIGINT NOT NULL REFERENCES produtos_finais(id),
            bom_id BIGINT NOT NULL REFERENCES bom(id),
            centro_trabalho_id BIGINT REFERENCES centros_de_trabalho(id),
            quantidade_planejada NUMERIC(14,3) NOT NULL CHECK (quantidade_planejada > 0),
            quantidade_produzida NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (quantidade_produzida >= 0),
            quantidade_refugada NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (quantidade_refugada >= 0),
            status VARCHAR(20) NOT NULL
                CHECK (status IN ('ABERTA','PLANEJADA','EM_PRODUCAO','PAUSADA','FINALIZADA','CANCELADA')),
            prioridade SMALLINT NOT NULL DEFAULT 3 CHECK (prioridade BETWEEN 1 AND 5),
            data_emissao DATE NOT NULL DEFAULT CURRENT_DATE,
            previsao_inicio TIMESTAMPTZ,
            previsao_fim TIMESTAMPTZ,
            inicio_real TIMESTAMPTZ,
            fim_real TIMESTAMPTZ,
            observacao TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ordens_operacoes (
            id BIGSERIAL PRIMARY KEY,
            ordem_id BIGINT NOT NULL REFERENCES ordens_de_producao(id) ON DELETE CASCADE,
            sequencia SMALLINT NOT NULL,
            centro_trabalho_id BIGINT NOT NULL REFERENCES centros_de_trabalho(id),
            setup_planejado_min NUMERIC(10,2) NOT NULL DEFAULT 0,
            ciclo_planejado_min NUMERIC(10,2) NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE'
                CHECK (status IN ('PENDENTE','EM_EXECUCAO','PAUSADA','CONCLUIDA')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (ordem_id, sequencia)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE apontamentos_producao (
            id BIGSERIAL PRIMARY KEY,
            ordem_operacao_id BIGINT NOT NULL REFERENCES ordens_operacoes(id) ON DELETE CASCADE,
            evento VARCHAR(20) NOT NULL CHECK (evento IN ('START','STOP','PAUSA','RETOMADA')),
            data_hora_evento TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            motivo VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE refugos_producao (
            id BIGSERIAL PRIMARY KEY,
            ordem_operacao_id BIGINT NOT NULL REFERENCES ordens_operacoes(id) ON DELETE CASCADE,
            quantidade NUMERIC(14,3) NOT NULL CHECK (quantidade > 0),
            motivo VARCHAR(200) NOT NULL,
            data_hora TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE estoque_lotes (
            id BIGSERIAL PRIMARY KEY,
            insumo_id BIGINT NOT NULL REFERENCES insumos(id),
            codigo_lote VARCHAR(40) NOT NULL UNIQUE,
            quantidade_inicial NUMERIC(14,4) NOT NULL CHECK (quantidade_inicial > 0),
            quantidade_disponivel NUMERIC(14,4) NOT NULL CHECK (quantidade_disponivel >= 0),
            largura_mm NUMERIC(10,2),
            altura_mm NUMERIC(10,2),
            espessura_mm NUMERIC(8,3),
            custo_total NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (custo_total >= 0),
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE estoque_movimentacoes (
            id BIGSERIAL PRIMARY KEY,
            lote_id BIGINT NOT NULL REFERENCES estoque_lotes(id),
            ordem_id BIGINT REFERENCES ordens_de_producao(id),
            tipo_movimento VARCHAR(30) NOT NULL
                CHECK (tipo_movimento IN ('ENTRADA','CONSUMO_OP','AJUSTE','RETALHO_GERADO','RETALHO_CONSUMIDO')),
            quantidade NUMERIC(14,4) NOT NULL CHECK (quantidade > 0),
            largura_mm NUMERIC(10,2),
            altura_mm NUMERIC(10,2),
            data_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            observacao VARCHAR(200)
        )
        """
    )

    op.execute("CREATE INDEX idx_bom_produto ON bom(produto_final_id, status)")
    op.execute("CREATE INDEX idx_bom_itens_bom ON bom_itens(bom_id, parent_item_id)")
    op.execute("CREATE INDEX idx_op_status ON ordens_de_producao(status, previsao_inicio)")
    op.execute(
        "CREATE INDEX idx_apontamentos_operacao_evento ON apontamentos_producao(ordem_operacao_id, data_hora_evento)"
    )
    op.execute("CREATE INDEX idx_mov_lote_data ON estoque_movimentacoes(lote_id, data_hora)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mov_lote_data")
    op.execute("DROP INDEX IF EXISTS idx_apontamentos_operacao_evento")
    op.execute("DROP INDEX IF EXISTS idx_op_status")
    op.execute("DROP INDEX IF EXISTS idx_bom_itens_bom")
    op.execute("DROP INDEX IF EXISTS idx_bom_produto")

    op.execute("DROP TABLE IF EXISTS estoque_movimentacoes")
    op.execute("DROP TABLE IF EXISTS estoque_lotes")
    op.execute("DROP TABLE IF EXISTS refugos_producao")
    op.execute("DROP TABLE IF EXISTS apontamentos_producao")
    op.execute("DROP TABLE IF EXISTS ordens_operacoes")
    op.execute("DROP TABLE IF EXISTS ordens_de_producao")
    op.execute("DROP TABLE IF EXISTS bom_itens")
    op.execute("DROP TABLE IF EXISTS bom")
    op.execute("DROP TABLE IF EXISTS produtos_finais")
    op.execute("DROP TABLE IF EXISTS centros_de_trabalho")
    op.execute("DROP TABLE IF EXISTS insumos")
    op.execute("DROP TABLE IF EXISTS clientes")
