set dotenv-load

# Every recipe stops on its own and asks for no input, so an agent shell never blocks.

default:
  @just --list

# Install all modules, create .env and give this checkout its own slot (ports, Compose project). Safe to run again.
setup:
  uv sync --locked --all-extras
  uv run --no-sync python scripts/dev_setup.py

# Build and start the core stack (api + migrations + postgres) in the background and wait until it is healthy.
# Give services to start only those. COMPOSE_PROFILES=workers also starts redis, workers and cron.
up *services:
  @uv run --no-sync python scripts/dev_setup.py --check
  docker compose up -d --build --wait {{ services }}
  @just urls

# Stop all services of this checkout, also the test database and the workers profile.
# `just down -v` also deletes the volumes of this checkout (its databases).
down *flags:
  docker compose --profile '*' down {{ flags }}

# Print recent logs and stop: `just logs api`. Add -f only to follow them.
logs *args:
  docker compose logs --tail=200 {{ args }}

# Show the state of the containers.
ps:
  docker compose ps

# Print the URLs and ports of this checkout.
urls:
  @echo "API       http://localhost:${API_PORT:-8000}  (docs: /docs, liveness: /up)"
  @echo "Postgres  localhost:${POSTGRES_PORT:-5432}  (test: ${POSTGRES_TEST_PORT:-5433})"
  @echo "Redis     localhost:${REDIS_PORT:-6379}  (workers profile)"

# Load the demo items into an empty database. Safe to run again.
seed:
  uv run --no-sync python -m scripts.seed

# Run the API on the host with auto-reload
app:
  uv run --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port ${API_PORT:-8000}

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

# Run tests (spins up the test database of this checkout)
test *flags="":
  @uv run --no-sync python scripts/dev_setup.py --check
  docker compose up postgres-test -d --wait
  uv run --no-sync pytest {{ flags }}

ci: lint types complexity test

# Print the scoped rules for the files you will change. Without files, print the whole map.
rules *paths:
  @uv run --no-sync python .agents/guidance.py {{ if paths == "" { "--index" } else { "--paths " + paths } }}

# Check the agent guidance: rules, links, repository paths and recipes. `just test` also runs it.
agents-check:
  uv run --no-sync python .agents/guidance.py --check

# Check the locked dependencies for known vulnerabilities (needs network). Not part of `just ci`.
audit:
  uv export --frozen --all-extras --no-emit-project --quiet | uvx pip-audit@2.10.1 --disable-pip -r /dev/stdin

# Apply migrations
migrate:
  uv run --no-sync alembic -c alembic/alembic.ini upgrade head

# Autogenerate a migration: just makemigration "create items table"
makemigration message:
  uv run --no-sync alembic -c alembic/alembic.ini revision --autogenerate -m "{{ message }}"
