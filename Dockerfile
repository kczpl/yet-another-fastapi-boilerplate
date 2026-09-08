FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Runtime image: no dev tooling (tests, linters). watchfiles used by docker-compose
# for reload comes with uvicorn[standard].
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY app ./app
COPY alembic ./alembic
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh && useradd --system --no-create-home app && chown app /app
USER app

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--port", "8000", "--host", "0.0.0.0"]
