# Roadmap Frontend (status atual e proximo passo)

## Status atual

O projeto esta com foco no backend e no dominio industrial.
As fases 0 a 7 entregaram:
- API completa por modulos de negocio,
- migrations e banco versionado,
- testes de integracao cobrindo fluxo ponta a ponta.

O frontend ainda **nao foi implementado** por decisao de sequenciamento:
primeiro consolidar regras criticas de negocio (BOM, custo, estoque, OP, MES e KPI),
depois construir UI sobre contratos de API estaveis.

## Objetivo do frontend (proxima etapa)

Construir um frontend web para uso de:
- PCP,
- estoque/compras,
- operador de maquina,
- gestao (indicadores).

## Stack sugerida para frontend

- React + Vite
- Tailwind CSS
- React Router
- React Query (ou fetch com camada customizada)
- Form state com validacao (react-hook-form + zod)

## Modulos de tela (ordem recomendada)

1. Autenticacao e layout base
2. Dashboard de KPI
3. Cadastros mestres
4. Engenharia BOM (arvore visual)
5. Orcamentos
6. Ordens de producao
7. MES (painel operador com botoes grandes Start/Stop/Pausa/Retomada)
8. Estoque e retalhos
9. Rastreabilidade consolidada

## Requisitos de UX para chao de fabrica

- Layout com alto contraste e botoes grandes.
- Feedback visual de status de maquina/operacao.
- Fluxo com poucos cliques.
- Modo tablet (resolucao 10-13 pol).
- Tolerancia a conexao instavel (retry e fila local de eventos, fase futura).

## Pronto para iniciar

Com os endpoints atuais, ja e possivel iniciar o frontend sem bloqueio.
Proximo passo tecnico: criar `apps/web` com scaffold React e conectar os primeiros fluxos:
- login (mock inicial),
- lista de OP,
- apontamento MES por operacao.
