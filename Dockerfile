FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY app ./app

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--port", "8000", "--host", "0.0.0.0"]
