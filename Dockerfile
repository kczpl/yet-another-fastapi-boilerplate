FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.6 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Runtime image: no development tooling (tests, linters).
COPY pyproject.toml uv.lock ./
ARG APP_EXTRA=""
RUN if [ -n "$APP_EXTRA" ]; then \
      uv sync --frozen --no-dev --no-cache --extra "$APP_EXTRA"; \
    else \
      uv sync --frozen --no-dev --no-cache; \
    fi

COPY app ./app
COPY alembic ./alembic
RUN useradd --system --no-create-home app && mkdir -p /var/lib/celery && chown app /app /var/lib/celery
USER app

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--port", "8000", "--host", "0.0.0.0"]
