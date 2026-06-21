.PHONY: run dev test evals lint format migrate docker-up docker-down

# Development
run:
	uvicorn codegraph.main:app --host 0.0.0.0 --port 8080 --reload

dev: docker-up run

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

# Testing
test:
	pytest tests/ -v --cov=src/codegraph

test-unit:
	pytest tests/unit/ -v

evals:
	python -m evals.run_evals

# Code quality
lint:
	ruff check src/ tests/
	mypy src/codegraph/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# Database
migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(msg)"

# Celery worker
worker:
	celery -A codegraph.tasks.celery_app worker --loglevel=info

# Frontend
frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Full stack
all: docker-up migrate run
