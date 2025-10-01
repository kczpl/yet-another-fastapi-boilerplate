
set dotenv-load

default:
  @just --list

compose:
  @docker compose up

app:
  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

workers:
  uv run pgq run app.workers.main:main --restart-on-failure

ruff:
  uv run ruff format
