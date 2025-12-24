
set dotenv-load

default:
  @just --list

compose:
  @docker compose up

app:
  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

ruff:
  uv run ruff format
