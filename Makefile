.PHONY: install lint test migrate up down

install:
	pip install -e "./apps/api[dev]"

lint:
	ruff check apps/api/src

test:
	pytest apps/api/src/tests -q

migrate:
	alembic -c db/migrations/alembic.ini upgrade head

up:
	docker compose -f infra/docker/docker-compose.yml up --build

down:
	docker compose -f infra/docker/docker-compose.yml down
