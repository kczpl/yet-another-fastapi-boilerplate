set dotenv-load

default:
  @just --list

# Start the full stack (api + workers + cron + postgres + redis)
compose:
  @docker compose up

# Run the API with auto-reload
app:
  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run Celery workers (all queues)
workers:
  uv run celery -A app.workers.celery:celery worker --loglevel=info -Q default,heavy

# Run the Celery beat scheduler
cron:
  uv run celery -A app.workers.celery:celery beat --loglevel=info

# Format + lint
ruff:
  uv run ruff format
  uv run ruff check

# Type-check
types:
  uvx pyright

# Run tests (spins up the test database)
test *flags="":
  docker compose up postgres-test -d
  uv run pytest {{ flags }}

ci: ruff types test

# Apply migrations
migrate:
  uv run alembic -c alembic/alembic.ini upgrade head

# Autogenerate a migration: just makemigration "create items table"
makemigration message:
  uv run alembic -c alembic/alembic.ini revision --autogenerate -m "{{ message }}"
