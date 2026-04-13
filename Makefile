.PHONY: help install dev backend frontend supabase-start supabase-stop migrate db-reset test lint fmt clean worker-publish deploy-checklist

help: ## Show this help message
	@echo "Cliplift — available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync
	cd frontend && npm install

supabase-start: ## Start local Supabase stack (Postgres + Auth + Storage)
	npx supabase start

supabase-stop: ## Stop local Supabase stack
	npx supabase stop

redis-start: ## Start local Redis (for rate-limiting in dev)
	docker compose up -d redis

redis-stop: ## Stop local Redis
	docker compose down

dev: ## Run backend and frontend dev servers concurrently
	@echo "Starting backend (:8000) and frontend (:3000)..."
	@(cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

backend: ## Run backend dev server only
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend: ## Run frontend dev server only
	cd frontend && npm run dev

migrate: ## Apply Alembic migrations
	cd backend && uv run alembic upgrade head

migrate-create: ## Create a new Alembic migration (usage: make migrate-create MSG="add foo")
	cd backend && uv run alembic revision --autogenerate -m "$(MSG)"

db-reset: ## Drop all tables and re-apply migrations
	cd backend && uv run alembic downgrade base && uv run alembic upgrade head

test: ## Run all tests
	cd backend && uv run pytest -v

lint: ## Lint backend (ruff) and frontend (eslint)
	cd backend && uv run ruff check .
	cd frontend && npm run lint

fmt: ## Format backend (ruff) and frontend (prettier)
	cd backend && uv run ruff format .
	cd frontend && npm run format

worker-publish: ## Manually trigger the publish-scheduled worker (dev only)
	@cd backend && uv run python -c "from app.config import settings; print(settings.ENCRYPTION_KEY)" | { \
		read TOKEN; \
		curl -X POST "http://localhost:8000/api/v1/workers/publish-scheduled?max_posts=10" \
			-H "X-Dev-Worker-Token: $$TOKEN"; \
	}

deploy-checklist: ## Print the Week 6 deploy checklist
	@echo "=== Cliplift Deploy Checklist ==="
	@echo ""
	@echo "1. Railway: connect repo, set root=backend/, start cmd: uv run uvicorn app.main:app --host 0.0.0.0 --port \$$PORT"
	@echo "2. Vercel: import repo, set root=frontend/, framework=Next.js"
	@echo "3. Set ALL production env vars in Railway (see docs/ENVIRONMENT.md)"
	@echo "4. Generate a FRESH ENCRYPTION_KEY for production (python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
	@echo "5. Run migrations: DATABASE_URL=<prod-url> cd backend && alembic upgrade head"
	@echo "6. Create Supabase Storage bucket: cliplift-videos (private)"
	@echo "7. Configure 4 QStash cron schedules (see docs/WORKERS.md)"
	@echo "8. Add Stripe webhook endpoint: https://api.cliplift.com/api/v1/billing/webhook"
	@echo "9. Update OAuth redirect URIs to production domain"
	@echo "10. Verify: curl https://api.cliplift.com/health"
	@echo ""
	@echo "Full guide: docs/DEPLOYMENT.md"

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.venv frontend/.next frontend/node_modules
