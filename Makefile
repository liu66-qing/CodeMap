.PHONY: run dev test lint format migrate docker-up docker-down

# Development
run:
	uvicorn src.evograph.main:app --host 0.0.0.0 --port 8080 --reload

dev: docker-up run

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

# Testing
test:
	pytest tests/ -v --cov=src/evograph

test-unit:
	pytest tests/unit/ -v

# Code quality
lint:
	ruff check src/ tests/
	mypy src/evograph/

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
	celery -A src.evograph.tasks.celery_app worker --loglevel=info

# Frontend
frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# Full stack
all: docker-up migrate run
