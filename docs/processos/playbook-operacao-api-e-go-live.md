# Playbook operacional da API (ERP Industrial)

Este documento consolida:
1. Sequencia de chamadas da API por processo.
2. Payloads de exemplo para cada etapa.
3. Checklist de go-live.

> Base URL local: `http://localhost:8000/api/v1`
>
> Header de perfil atual (ambiente dev): `X-User-Role`

---

## 1) Sequencia operacional ponta a ponta (API)

## 1.1 Cadastros base

### 1) Criar cliente

`POST /cadastro/clientes`

```json
{
  "codigo": "CLI-001",
  "razao_social": "Industria Exemplo LTDA"
}
```

### 2) Criar insumo

`POST /cadastro/insumos`

```json
{
  "codigo": "INS-001",
  "descricao": "Chapa Aco Carbono 2mm",
  "categoria": "CHAPA",
  "unidade_medida": "UN",
  "custo_unitario": "10.00"
}
```

### 3) Criar centro de trabalho

`POST /cadastro/centros-trabalho`

```json
{
  "codigo": "CT-ROUTER-01",
  "nome": "Router CNC 01",
  "tipo_maquina": "ROUTER_CNC",
  "taxa_horaria": "120.00",
  "setup_padrao_min": 10,
  "capacidade_horas_dia": "8"
}
```

### 4) Criar produto final

`POST /cadastro/produtos-finais`

```json
{
  "codigo": "PRD-001",
  "descricao": "Equipamento Industrial A",
  "unidade_medida": "UN",
  "margem_lucro_padrao_pct": "25.00"
}
```

---

## 1.2 Engenharia BOM

### 5) Criar BOM do produto

`POST /engenharia-bom/boms`

```json
{
  "produto_final_id": 1
}
```

### 6) Incluir item de BOM (insumo)

`POST /engenharia-bom/boms/{bom_id}/itens`

```json
{
  "item_tipo": "INSUMO",
  "insumo_id": 1,
  "quantidade": "2.00",
  "perda_pct": "10.00"
}
```

### 7) Validar arvore e explosao

- `GET /engenharia-bom/boms/{bom_id}/arvore`
- `GET /engenharia-bom/boms/{bom_id}/explosao?quantidade_base=10`

---

## 1.3 Orcamento

### 8) Simular custo/preco

`POST /orcamentos/simulacoes`

```json
{
  "cliente_id": 1,
  "produto_final_id": 1,
  "bom_id": 1,
  "quantidade": "10",
  "margem_lucro_pct": "20",
  "custo_indireto_fixo": "15",
  "custo_indireto_pct": "5",
  "operacoes": [
    {
      "centro_trabalho_id": 1,
      "setup_min": "10",
      "ciclo_min": "2"
    }
  ]
}
```

### 9) Criar orcamento versionado

`POST /orcamentos`

```json
{
  "codigo": "ORC-001",
  "cliente_id": 1,
  "produto_final_id": 1,
  "bom_id": 1,
  "quantidade": "10",
  "margem_lucro_pct": "20",
  "custo_indireto_fixo": "15",
  "custo_indireto_pct": "5",
  "operacoes": [
    {
      "centro_trabalho_id": 1,
      "setup_min": "10",
      "ciclo_min": "2"
    }
  ]
}
```

### 10) Gerar nova versao de orcamento (recalculo)

`POST /orcamentos/{orcamento_id}/versoes`

```json
{
  "bom_id": 1,
  "quantidade": "12",
  "margem_lucro_pct": "22",
  "custo_indireto_fixo": "20",
  "custo_indireto_pct": "6",
  "operacoes": [
    {
      "centro_trabalho_id": 1,
      "setup_min": "10",
      "ciclo_min": "2.2"
    }
  ]
}
```

---

## 1.4 Estoque e retalhos

### 11) Entrada de lote

`POST /estoque-retalhos/lotes`

```json
{
  "insumo_id": 1,
  "codigo_lote": "L-001",
  "quantidade_inicial": "20",
  "custo_total": "200"
}
```

### 12) Gerar retalho

`POST /estoque-retalhos/lotes/{lote_id}/retalhos`

```json
{
  "codigo_lote_retalho": "RET-001-A",
  "quantidade": "5",
  "ordem_id": 1
}
```

### 13) Consumir lote/retalho na OP

`POST /estoque-retalhos/lotes/{lote_id}/consumos`

```json
{
  "quantidade": "8",
  "ordem_id": 1
}
```

---

## 1.5 Ordem de producao

### 14) Emitir OP com snapshot BOM

`POST /ordens-producao`

```json
{
  "numero_op": "OP-001",
  "cliente_id": 1,
  "produto_final_id": 1,
  "bom_id": 1,
  "quantidade_planejada": "10",
  "prioridade": 2,
  "operacoes": [
    {
      "centro_trabalho_id": 1,
      "setup_planejado_min": "10",
      "ciclo_planejado_min": "2"
    }
  ]
}
```

### 15) Avancar status da OP

`PATCH /ordens-producao/{ordem_id}/status`

```json
{
  "status": "EM_PRODUCAO"
}
```

---

## 1.6 MES

### 16) Start/Stop/Pausa/Retomada

`POST /mes-apontamentos/operacoes/{ordem_operacao_id}/eventos`

```json
{
  "evento": "START",
  "data_hora_evento": "2026-02-16T08:00:00Z"
}
```

```json
{
  "evento": "PAUSA",
  "data_hora_evento": "2026-02-16T08:20:00Z",
  "motivo": "Troca de ferramenta"
}
```

```json
{
  "evento": "RETOMADA",
  "data_hora_evento": "2026-02-16T08:30:00Z"
}
```

```json
{
  "evento": "STOP",
  "data_hora_evento": "2026-02-16T09:00:00Z",
  "quantidade_produzida": "8"
}
```

### 17) Registrar refugo

`POST /mes-apontamentos/operacoes/{ordem_operacao_id}/refugos`

```json
{
  "quantidade": "2",
  "motivo": "Peca fora de medida"
}
```

---

## 1.7 Indicadores e rastreabilidade

### 18) KPI agregado

`GET /indicadores/kpis`

Exemplo com filtros:

`GET /indicadores/kpis?periodo_inicio=2026-02-01&periodo_fim=2026-02-29&status=FINALIZADA`

### 19) KPI por OP

`GET /indicadores/ordens?page=1&page_size=20&search=OP-001`

### 20) Rastreabilidade de OP

`GET /indicadores/rastreabilidade/ordens/{ordem_id}`

Retorna:
- snapshot BOM congelado na emissao,
- resumo de operacoes e tempos MES,
- movimentacoes de estoque ligadas a ordem,
- lotes relacionados e fluxo de retalho.

---

## 2) Runbook rapido de operacao

## 2.1 Abertura diaria
1. Validar saude: `GET /health`.
2. Validar saldo critico: `GET /estoque-retalhos/saldos/insumos`.
3. Listar OPs planejadas: `GET /ordens-producao?status=PLANEJADA`.

## 2.2 Fechamento diario
1. Confirmar operacoes sem STOP:
   - `GET /mes-apontamentos/operacoes/{id}/resumo-tempo` (operacoes ativas).
2. Conferir refugos do dia:
   - `GET /mes-apontamentos/operacoes/{id}/refugos`.
3. Consolidar KPI diario:
   - `GET /indicadores/kpis?periodo_inicio=YYYY-MM-DD&periodo_fim=YYYY-MM-DD`.

## 2.3 Reprocesso padrao
1. Se houve erro de apontamento, registrar evento corretivo com motivo.
2. Se houve divergencia fisica de estoque, registrar ajuste:
   - `POST /estoque-retalhos/lotes/{lote_id}/ajustes`.
3. Recalcular KPI apos ajuste (endpoint de indicadores).

---

## 3) Checklist de go-live (producao)

## 3.1 Banco e migrations
- [ ] Backup full validado antes do deploy.
- [ ] `alembic upgrade head` executado com sucesso.
- [ ] Plano de rollback de migration definido.

## 3.2 API e seguranca
- [ ] Trocar header `X-User-Role` por autenticacao JWT real.
- [ ] Politica de senha e expiracao de token definida.
- [ ] CORS e variaveis de ambiente travadas por ambiente.

## 3.3 Observabilidade
- [ ] Logs estruturados com correlation id.
- [ ] Metricas de erro, latencia e throughput em dashboard.
- [ ] Alertas para falha de apontamento MES e erro de estoque.

## 3.4 Carga e performance
- [ ] Teste de carga em eventos MES concorrentes.
- [ ] Indices revisados com plano de execucao real.
- [ ] P95/P99 dos endpoints criticos dentro da meta.

## 3.5 Operacao industrial
- [ ] Treinamento operador: fluxo Start/Pausa/Retomada/Stop.
- [ ] Treinamento PCP: emissao OP e fechamento.
- [ ] Treinamento estoque: lote, consumo, retalho e ajuste.

## 3.6 Governanca
- [ ] Dicionario de motivos de refugo aprovado.
- [ ] Regra de fechamento de OP documentada.
- [ ] Matriz de responsabilidade (quem pode fazer o que) definida.

---

## 4) Curls de referencia

Exemplo rapido (ambiente local):

```bash
curl -X GET "http://localhost:8000/health"
```

```bash
curl -X GET "http://localhost:8000/api/v1/indicadores/kpis" \
  -H "X-User-Role: admin"
```

```bash
curl -X GET "http://localhost:8000/api/v1/indicadores/rastreabilidade/ordens/1" \
  -H "X-User-Role: admin"
```

