FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/

# Copy mode: the cache mount is not in the final image. Bytecode makes the start faster.
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Runtime packages only: no development tooling (tests, linters).
COPY pyproject.toml uv.lock ./
ARG APP_EXTRA=""
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -n "$APP_EXTRA" ]; then \
      uv sync --frozen --no-dev --extra "$APP_EXTRA"; \
    else \
      uv sync --frozen --no-dev; \
    fi

# The same base image as the build stage: the virtual environment links to its Python.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN useradd --system --no-create-home app && mkdir -p /var/lib/celery && chown app /app /var/lib/celery
COPY --from=build /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
USER app

# On SIGTERM, Uvicorn cancels the open requests after 25 s and then closes the database pool.
# Set a stop timeout above 25 s. Kubernetes and ECS wait 30 s; `docker stop` waits only 10 s.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "25"]
