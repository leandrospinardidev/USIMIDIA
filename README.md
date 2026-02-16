# ERP Industrial

Base inicial do ERP web para controle de usinagem CNC, montagem e chao de fabrica.

## Estrutura

- `apps/api`: backend FastAPI
- `apps/web`: frontend web (React + Tailwind, painel MES inicial entregue)
- `db/migrations`: migrations Alembic
- `db/ddl`: referencia de DDL
- `infra/docker`: docker compose para desenvolvimento local
- `docs`: documentos de arquitetura e banco

## Documentos recomendados

- `docs/processos/playbook-operacao-api-e-go-live.md`
- `docs/processos/deploy-vps-nginx.md`
- `docs/arquitetura/roadmap-frontend.md`

## Subir ambiente local

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

## Subir ambiente de producao (compose)

```bash
cd infra/docker
cp env.prod.example .env.prod
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## Rodar migrations

```bash
alembic -c db/migrations/alembic.ini upgrade head
```

## Rodar testes da API

```bash
pip install -e "./apps/api[dev]"
pytest apps/api/src/tests -q
```

## Rodar frontend web

```bash
cd apps/web
npm install
npm run dev
```
