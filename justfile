set dotenv-load

default:
  @just --list

# Start the core stack (api + migrations + postgres)
compose:
  @docker compose up

# Run the API with auto-reload
app:
  uv run --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run Celery workers (all queues)
workers:
  uv run --no-sync celery -A app.workers.celery:celery worker --loglevel=info -Q default,heavy

# Run the Celery beat scheduler
cron:
  uv run --no-sync celery -A app.workers.celery:celery beat --loglevel=info

# Format + lint, fixing what can be fixed
ruff:
  uv run --no-sync ruff format
  uv run --no-sync ruff check --fix

# Lint without touching files (what CI runs)
lint:
  uv run --no-sync ruff format --check
  uv run --no-sync ruff check

# Type-check
types:
  uv run --no-sync pyright

# Cognitive complexity gate — limit and paths in pyproject.toml ([tool.complexipy])
complexity:
  uv run --no-sync complexipy

# Run tests (spins up the test database)
test *flags="":
  docker compose up postgres-test -d --wait
  uv run --no-sync pytest {{ flags }}

ci: lint types complexity test

# Apply migrations
migrate:
  uv run --no-sync alembic -c alembic/alembic.ini upgrade head

# Autogenerate a migration: just makemigration "create items table"
makemigration message:
  uv run --no-sync alembic -c alembic/alembic.ini revision --autogenerate -m "{{ message }}"
