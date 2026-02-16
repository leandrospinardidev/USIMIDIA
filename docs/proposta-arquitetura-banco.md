# Proposta inicial de arquitetura e banco de dados (ERP Industrial)

## 1) Decisao de stack e principios

Para esta fase, recomendo **Backend em Python + FastAPI** com **PostgreSQL**.

Motivos:
- Excelente produtividade para API REST.
- Tipagem com Pydantic ajuda a reduzir erro de integracao.
- Bom ecossistema para filas, integracoes e analytics.
- Facil escalar de monolito modular para servicos separados no futuro.

Principios de arquitetura:
- **Monolito modular** (inicio rapido, operacao simples, fronteiras claras).
- **Clean Architecture por modulo** (domain / application / infra / presentation).
- **Migrations versionadas** (Alembic) e sem alteracao manual em producao.
- **Auditoria e rastreabilidade** desde o inicio (created_at, updated_at, status, snapshots).
- **Versionamento de BOM** e congelamento de estrutura em OP para preservar historico.

---

## 2) Estrutura de pastas recomendada

```txt
erp-industrial/
├── apps/
│   ├── api/                               # FastAPI
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── core/
│   │   │   │   ├── config.py
│   │   │   │   ├── security.py
│   │   │   │   ├── database.py
│   │   │   │   ├── logging.py
│   │   │   │   └── exceptions.py
│   │   │   ├── shared/
│   │   │   │   ├── domain/
│   │   │   │   ├── application/
│   │   │   │   └── infrastructure/
│   │   │   ├── modules/
│   │   │   │   ├── cadastro/              # clientes, produtos, insumos, centros
│   │   │   │   │   ├── domain/
│   │   │   │   │   ├── application/
│   │   │   │   │   ├── infrastructure/
│   │   │   │   │   └── presentation/
│   │   │   │   ├── engenharia_bom/
│   │   │   │   ├── estoque_retalhos/
│   │   │   │   ├── orcamentos/
│   │   │   │   ├── ordens_producao/
│   │   │   │   └── mes_apontamentos/
│   │   │   └── tests/
│   │   │       ├── unit/
│   │   │       ├── integration/
│   │   │       └── contract/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── web/                               # Frontend futuro (nao implementar agora)
│       ├── src/
│       └── package.json
├── db/
│   ├── migrations/                        # Alembic versions
│   ├── seed/
│   ├── ddl/
│   │   └── 001_base_schema.sql
│   └── diagrams/
├── docs/
│   ├── arquitetura/
│   ├── banco/
│   └── processos/
├── infra/
│   ├── docker/
│   │   └── docker-compose.yml             # api + postgres + redis
│   ├── k8s/
│   └── ci/
├── scripts/
│   ├── dev/
│   └── db/
└── README.md
```

---

## 3) Modelagem inicial do banco (PostgreSQL)

> Abaixo esta o schema inicial com as tabelas pedidas (Clientes, Insumos, Centros_de_Trabalho, Produtos_Finais, BOM e Ordens_de_Producao) e tabelas de apoio minimas para viabilizar multi-nivel de BOM e apontamento de producao.

```sql
-- opcional para UUID; nesta proposta usamos BIGSERIAL
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE clientes (
    id                  BIGSERIAL PRIMARY KEY,
    codigo              VARCHAR(30) NOT NULL UNIQUE,
    razao_social        VARCHAR(150) NOT NULL,
    nome_fantasia       VARCHAR(150),
    cnpj_cpf            VARCHAR(20) UNIQUE,
    email               VARCHAR(150),
    telefone            VARCHAR(30),
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE insumos (
    id                  BIGSERIAL PRIMARY KEY,
    codigo              VARCHAR(30) NOT NULL UNIQUE,
    descricao           VARCHAR(200) NOT NULL,
    categoria           VARCHAR(30) NOT NULL CHECK (
                            categoria IN ('CHAPA','PERFIL','PARAFUSO','ELETRONICO','QUIMICO','OUTRO')
                        ),
    unidade_medida      VARCHAR(10) NOT NULL, -- UN, KG, M, M2, M3
    custo_unitario      NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (custo_unitario >= 0),
    controla_lote       BOOLEAN NOT NULL DEFAULT TRUE,
    largura_mm          NUMERIC(10,2),
    altura_mm           NUMERIC(10,2),
    espessura_mm        NUMERIC(8,3),
    estoque_minimo      NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE centros_de_trabalho (
    id                  BIGSERIAL PRIMARY KEY,
    codigo              VARCHAR(30) NOT NULL UNIQUE,
    nome                VARCHAR(120) NOT NULL,
    tipo_maquina        VARCHAR(30) NOT NULL CHECK (
                            tipo_maquina IN ('ROUTER_CNC','LASER_CO2','TORNO_CNC','FRESA_CNC','MONTAGEM','INSPECAO')
                        ),
    taxa_horaria        NUMERIC(12,2) NOT NULL CHECK (taxa_horaria >= 0),
    setup_padrao_min    INTEGER NOT NULL DEFAULT 0 CHECK (setup_padrao_min >= 0),
    capacidade_horas_dia NUMERIC(6,2) NOT NULL DEFAULT 8 CHECK (capacidade_horas_dia > 0),
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE produtos_finais (
    id                          BIGSERIAL PRIMARY KEY,
    codigo                      VARCHAR(40) NOT NULL UNIQUE,
    descricao                   VARCHAR(200) NOT NULL,
    revisao_atual               VARCHAR(10) NOT NULL DEFAULT 'A',
    unidade_medida              VARCHAR(10) NOT NULL DEFAULT 'UN',
    margem_lucro_padrao_pct     NUMERIC(6,2) NOT NULL DEFAULT 30 CHECK (margem_lucro_padrao_pct >= 0),
    ativo                       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cabecalho de versao de BOM
CREATE TABLE bom (
    id                  BIGSERIAL PRIMARY KEY,
    produto_final_id    BIGINT NOT NULL REFERENCES produtos_finais(id),
    versao              INTEGER NOT NULL,
    status              VARCHAR(20) NOT NULL CHECK (status IN ('RASCUNHO','ATIVA','OBSOLETA')),
    valido_de           DATE NOT NULL DEFAULT CURRENT_DATE,
    valido_ate          DATE,
    observacao          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (produto_final_id, versao)
);

-- Itens da arvore de BOM (multi nivel por parent_item_id)
CREATE TABLE bom_itens (
    id                      BIGSERIAL PRIMARY KEY,
    bom_id                  BIGINT NOT NULL REFERENCES bom(id) ON DELETE CASCADE,
    parent_item_id          BIGINT REFERENCES bom_itens(id) ON DELETE CASCADE,
    ordem                   SMALLINT NOT NULL DEFAULT 1,
    item_tipo               VARCHAR(20) NOT NULL CHECK (item_tipo IN ('INSUMO','SUBCONJUNTO')),
    insumo_id               BIGINT REFERENCES insumos(id),
    produto_filho_id        BIGINT REFERENCES produtos_finais(id),
    quantidade              NUMERIC(14,4) NOT NULL CHECK (quantidade > 0),
    unidade_medida          VARCHAR(10) NOT NULL,
    perda_pct               NUMERIC(6,2) NOT NULL DEFAULT 0 CHECK (perda_pct >= 0 AND perda_pct <= 100),
    observacao              TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (item_tipo = 'INSUMO' AND insumo_id IS NOT NULL AND produto_filho_id IS NULL)
        OR
        (item_tipo = 'SUBCONJUNTO' AND produto_filho_id IS NOT NULL AND insumo_id IS NULL)
    )
);

CREATE TABLE ordens_de_producao (
    id                      BIGSERIAL PRIMARY KEY,
    numero_op               VARCHAR(30) NOT NULL UNIQUE,
    cliente_id              BIGINT REFERENCES clientes(id),
    produto_final_id        BIGINT NOT NULL REFERENCES produtos_finais(id),
    bom_id                  BIGINT NOT NULL REFERENCES bom(id), -- snapshot de versao usada
    centro_trabalho_id      BIGINT REFERENCES centros_de_trabalho(id),
    quantidade_planejada    NUMERIC(14,3) NOT NULL CHECK (quantidade_planejada > 0),
    quantidade_produzida    NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (quantidade_produzida >= 0),
    quantidade_refugada     NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (quantidade_refugada >= 0),
    status                  VARCHAR(20) NOT NULL CHECK (
                                status IN ('ABERTA','PLANEJADA','EM_PRODUCAO','PAUSADA','FINALIZADA','CANCELADA')
                            ),
    prioridade              SMALLINT NOT NULL DEFAULT 3 CHECK (prioridade BETWEEN 1 AND 5),
    data_emissao            DATE NOT NULL DEFAULT CURRENT_DATE,
    previsao_inicio         TIMESTAMPTZ,
    previsao_fim            TIMESTAMPTZ,
    inicio_real             TIMESTAMPTZ,
    fim_real                TIMESTAMPTZ,
    observacao              TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Operacoes por OP (roteiro simplificado por centro de trabalho)
CREATE TABLE ordens_operacoes (
    id                      BIGSERIAL PRIMARY KEY,
    ordem_id                BIGINT NOT NULL REFERENCES ordens_de_producao(id) ON DELETE CASCADE,
    sequencia               SMALLINT NOT NULL,
    centro_trabalho_id      BIGINT NOT NULL REFERENCES centros_de_trabalho(id),
    setup_planejado_min     NUMERIC(10,2) NOT NULL DEFAULT 0,
    ciclo_planejado_min     NUMERIC(10,2) NOT NULL DEFAULT 0,
    status                  VARCHAR(20) NOT NULL DEFAULT 'PENDENTE'
                                CHECK (status IN ('PENDENTE','EM_EXECUCAO','PAUSADA','CONCLUIDA')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ordem_id, sequencia)
);

-- Eventos MES start/stop/pause para rastrear tempo real
CREATE TABLE apontamentos_producao (
    id                      BIGSERIAL PRIMARY KEY,
    ordem_operacao_id       BIGINT NOT NULL REFERENCES ordens_operacoes(id) ON DELETE CASCADE,
    evento                  VARCHAR(20) NOT NULL CHECK (evento IN ('START','STOP','PAUSA','RETOMADA')),
    data_hora_evento        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    motivo                  VARCHAR(200),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE refugos_producao (
    id                      BIGSERIAL PRIMARY KEY,
    ordem_operacao_id       BIGINT NOT NULL REFERENCES ordens_operacoes(id) ON DELETE CASCADE,
    quantidade              NUMERIC(14,3) NOT NULL CHECK (quantidade > 0),
    motivo                  VARCHAR(200) NOT NULL,
    data_hora               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Controle de lotes de insumo (inclui chapa inteira de entrada)
CREATE TABLE estoque_lotes (
    id                      BIGSERIAL PRIMARY KEY,
    insumo_id               BIGINT NOT NULL REFERENCES insumos(id),
    codigo_lote             VARCHAR(40) NOT NULL UNIQUE,
    quantidade_inicial      NUMERIC(14,4) NOT NULL CHECK (quantidade_inicial > 0),
    quantidade_disponivel   NUMERIC(14,4) NOT NULL CHECK (quantidade_disponivel >= 0),
    largura_mm              NUMERIC(10,2),
    altura_mm               NUMERIC(10,2),
    espessura_mm            NUMERIC(8,3),
    custo_total             NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (custo_total >= 0),
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Movimentacoes de estoque e retalhos
CREATE TABLE estoque_movimentacoes (
    id                      BIGSERIAL PRIMARY KEY,
    lote_id                 BIGINT NOT NULL REFERENCES estoque_lotes(id),
    ordem_id                BIGINT REFERENCES ordens_de_producao(id),
    tipo_movimento          VARCHAR(30) NOT NULL CHECK (
                                tipo_movimento IN ('ENTRADA','CONSUMO_OP','AJUSTE','RETALHO_GERADO','RETALHO_CONSUMIDO')
                            ),
    quantidade              NUMERIC(14,4) NOT NULL CHECK (quantidade > 0),
    largura_mm              NUMERIC(10,2),
    altura_mm               NUMERIC(10,2),
    data_hora               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    observacao              VARCHAR(200)
);

CREATE INDEX idx_bom_produto ON bom(produto_final_id, status);
CREATE INDEX idx_bom_itens_bom ON bom_itens(bom_id, parent_item_id);
CREATE INDEX idx_op_status ON ordens_de_producao(status, previsao_inicio);
CREATE INDEX idx_apontamentos_operacao_evento ON apontamentos_producao(ordem_operacao_id, data_hora_evento);
CREATE INDEX idx_mov_lote_data ON estoque_movimentacoes(lote_id, data_hora);
```

### Relacionamentos principais

- `clientes (1) -> (N) ordens_de_producao`
- `produtos_finais (1) -> (N) bom`
- `bom (1) -> (N) bom_itens`
- `bom_itens (1) -> (N) bom_itens` via `parent_item_id` (arvore multi nivel)
- `insumos (1) -> (N) bom_itens` para itens de materia-prima
- `ordens_de_producao (1) -> (N) ordens_operacoes`
- `ordens_operacoes (1) -> (N) apontamentos_producao`
- `ordens_operacoes (1) -> (N) refugos_producao`
- `insumos (1) -> (N) estoque_lotes`
- `estoque_lotes (1) -> (N) estoque_movimentacoes`

---

## 4) Plano de acao (ordem recomendada de implementacao)

## Fase 0 - Fundacao tecnica (Sprint 0)
1. Subir base do projeto (FastAPI, PostgreSQL, Alembic, Docker Compose, lint e testes).
2. Definir convencoes: erros padrao, paginacao, filtros, logs, timezone (UTC).
3. Implementar modulo de autenticacao/autorizacao simples (RBAC por perfil: admin, pcp, operador, compras).
4. Entregar pipeline CI com testes + migration check.

## Fase 1 - Cadastros mestres (base de todos os modulos)
1. CRUD de `clientes`, `insumos`, `centros_de_trabalho`, `produtos_finais`.
2. Validacoes de negocio (codigo unico, status ativo/inativo, unidade de medida).
3. Testes de integracao para garantir consistencia do banco.

**Por que primeiro?**
Sem dados mestres consistentes, BOM, orcamentos e OP nao tem base confiavel.

## Fase 2 - Engenharia de Produto (BOM multi nivel)
1. CRUD de `bom` e `bom_itens` com versoes.
2. API para montar e consultar arvore completa.
3. Regra de negocio: impedir ciclo (A -> B -> A).
4. Funcao de "explosao de BOM" para listar consumo total por insumo.

**Entrega critica:** versionamento de BOM + explosao valida.

## Fase 3 - Estoque e retalhos
1. Entrada de lotes (`estoque_lotes`) com dimensoes e custo.
2. Movimentacoes (`estoque_movimentacoes`) ligadas a OP.
3. Logica de fracionamento para chapas e geracao de retalhos.
4. Saldo disponivel em tempo real por insumo/lote.

**Entrega critica:** rastreabilidade completa de consumo de materia-prima.

## Fase 4 - Gerador de Orcamentos
1. Motor de custo: material (BOM) + tempo de maquina (taxa horaria) + margem.
2. Simulacao por centro de trabalho/roteiro.
3. Persistencia de versao de calculo para auditoria comercial.

Formula base:
`preco_venda = (custo_material + custo_maquina + custo_indireto) * (1 + margem)`

## Fase 5 - Ordens de Producao
1. Emissao de OP com snapshot da BOM usada.
2. Planejamento de operacoes por centro de trabalho (`ordens_operacoes`).
3. Controle de status (aberta -> em producao -> finalizada).

## Fase 6 - MES (apontamento de chao de fabrica)
1. API/servico para eventos Start/Stop/Pausa/Retomada.
2. Calculo de tempo real por operacao/maquina.
3. Registro de refugo e motivos.
4. Atualizacao automatica da OP com produzido/refugado.

## Fase 7 - Indicadores e consolidacao
1. Indicadores: eficiencia, tempo planejado vs real, refugo, custo real vs orcado.
2. Relatorios de rastreabilidade (OP -> lote -> consumo -> retalho).
3. Ajustes de performance e indices conforme carga real.

---

## 5) Recomendacoes tecnicas para escalar sem retrabalho

- Usar `NUMERIC` para quantidades e custos (evitar float em dados industriais).
- Salvar sempre timestamps em UTC.
- Implementar lock otimista (`updated_at`/versao) para evitar conflito de edicao de BOM.
- Toda OP deve guardar referencia da BOM/versao usada no momento da emissao.
- Criar suite de testes de regras de negocio (nao apenas teste de endpoint).
- Adotar event log para auditoria de eventos criticos (mudanca BOM, inicio/fim OP, ajustes de estoque).

---

## 6) Resultado esperado desta fase de arquitetura

Ao final desta etapa de definicao, teremos:
1. Estrutura de projeto pronta para iniciar desenvolvimento em camadas.
2. Modelo relacional inicial cobrindo BOM, custo, estoque, OP e MES.
3. Ordem de implementacao que reduz risco e evita retrabalho.

