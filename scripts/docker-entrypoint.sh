#!/bin/bash
set -e

echo "Running database migrations..."
/app/.venv/bin/alembic -c alembic/alembic.ini upgrade head

echo "Starting application..."
exec "$@"
