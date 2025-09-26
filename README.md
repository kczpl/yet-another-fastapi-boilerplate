# Sample AI Agents app with AWS Fargate

Simple app to build AI agents with Python, uv, FastAPI and AWS Fargate.

TODO: debtor update - done
TODO: update comms as cancelled
TODO: mark as paid
TODO: update invoice due data, issue date, total debt ammount remaining debt, currency and description
TODO: filters
TODO: settings - get organization settings and update them

```sh
# init venv
uv venv .venv

# run venv
source .venv/bin/activate

# install packages
uv sync

# run fastapi
uv run fastapi dev
```

Place your envs in .env in:
```
backend
├── app
├── .env
├── justfile
├── pyproject.toml
├── README.md
...
└── uv.lock
```

Envs are sourced in `backend/app/core/config.py` and names must match `Settings` class.

  <!-- # Run migrations
  uv run alembic upgrade head

  # Check migration status
  uv run alembic current

  # View history
  uv run alembic history -->

---

## uv

Add packages to your project:
```sh
uv add fastapi uvicorn sqlalchemy pydantic
```

Install all dependencies from pyproject.toml:
```sh
uv pip install -e .
```

Install dev dependencies:
```sh
uv pip install -e ".[dev]"
```

Add dev dependencies:
```sh
uv add --dev pytest black mypy isort
```

Linting:
```sh
# Basic linting:
ruff check .

# Format code
ruff format .

# Check and fix automatically fixable issues
ruff check --fix .

# Run with specific rules
ruff check --select E,F,I .

# Run with specific configuration file
ruff check --config ruff.toml .
```
## Build and deploy with Docker

To deploy as a Docker image, build the image and push it to AWS Elastic Container Registry (ECR).

To build the image for AWS Lambda:

```sh
uv lock
docker build -t fastapi-app .
```

To push the image to AWS Elastic Container Registry (ECR)

```sh
aws ecr get-login-password --region region | docker login --username AWS --password-stdin aws_account_id.dkr.ecr.region.amazonaws.com
docker tag fastapi-app:latest aws_account_id.dkr.ecr.region.amazonaws.com/fastapi-app:latest
docker push aws_account_id.dkr.ecr.region.amazonaws.com/fastapi-app:latest
```
