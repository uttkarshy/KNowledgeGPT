.PHONY: up down logs migrate shell-backend shell-db build clean

up: ## Start all services (Postgres, Redis, ClamAV, backend, worker, frontend)
	docker compose up --build

up-d: ## Same, detached
	docker compose up --build -d

down: ## Stop and remove all containers (keeps named volumes / data)
	docker compose down

clean: ## Stop and remove containers AND volumes — wipes all data
	docker compose down -v

logs: ## Tail logs from all services
	docker compose logs -f

logs-backend:
	docker compose logs -f backend celery-worker

migrate: ## Run Alembic migrations manually (normally automatic on backend startup)
	docker compose exec backend alembic upgrade head

migration: ## Generate a new Alembic migration: make migration name="add foo column"
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

shell-backend: ## Open a shell in the backend container
	docker compose exec backend /bin/bash

shell-db: ## Open a psql shell against the dev database
	docker compose exec postgres psql -U knowledgegpt -d knowledgegpt

build: ## Rebuild images without starting
	docker compose build
