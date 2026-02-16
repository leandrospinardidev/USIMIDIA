# ERP Industrial

Base inicial do ERP web para controle de usinagem CNC, montagem e chao de fabrica.

## Estrutura

- `apps/api`: backend FastAPI
- `db/migrations`: migrations Alembic
- `db/ddl`: referencia de DDL
- `infra/docker`: docker compose para desenvolvimento local
- `docs`: documentos de arquitetura e banco

## Subir ambiente local

```bash
docker compose -f infra/docker/docker-compose.yml up --build
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
