# ERP Industrial API

Backend em FastAPI para o ERP industrial.

## Requisitos

- Python 3.11+
- PostgreSQL 16+

## Rodar local

```bash
pip install -e ".[dev]"
uvicorn main:app --app-dir src --reload --host 0.0.0.0 --port 8000
```

## Banco e migrations

```bash
alembic -c ../../db/migrations/alembic.ini upgrade head
```
