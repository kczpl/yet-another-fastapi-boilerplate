# Start a new project from the template

Do these steps once, in the first commits of the new project. Read the whole file first. Run
`just ci` after each section. The last section deletes this file.

## 1. Name the project

- `pyproject.toml`: set `name` and `description`. Then run `uv lock`.
- `app/main.py`: set the `title` of the FastAPI object.
- `README.md`: write the title and the introduction of your project. Remove the section
  "This template".

The package directory stays `app/`. The Compose project name comes from the name of the
checkout directory. The local database keeps the name `app`: only your machine uses it.

## 2. Remove the example feature

Delete the files of the example:

```bash
git rm -r -q app/features/items tests/features/items tests/factories/item.py \
  tests/scripts/test_seed.py alembic/versions/2026_06_13_0900-0001_initial_create_items_table.py
```

Remove the example from the shared files:

| File | Remove |
|---|---|
| `app/api/__init__.py` | The items router and the `ai_routes` block. |
| `app/models.py` | `Item`. `__all__` stays, also when it is empty. |
| `app/core/errors.py` | The items section of `ERRORS`. |
| `app/workers/registry.py` | `summarize_item_task` and `example_cleanup_task`. |
| `app/workers/enqueue.py` | `enqueue_summarize_item` and its import. |
| `app/workers/celery.py` | The `example-cleanup` beat entry. |
| `scripts/seed.py` | The items code. `seed()` returns 0 until a feature has demo data. |
| `tests/architecture/test_route_inventory.py` | The items routes in `PUBLIC_ROUTES` and `AI_ROUTES`. |

The rules use the example as an illustration. Find these places with
`grep -rn -i item AGENTS.md .agents/rules` and replace them with your own code, or remove them.

The infrastructure tests use their own throwaway routes and tables. The guard tests also pass
without a feature, a repository or a migration.

## 3. Remove the AI extra (optional)

Keep the `ai` extra when the project calls a model. If not:

```bash
git rm -q app/core/agents.py .agents/rules/backend/ai-agents.md
```

- `app/core/config.py`: remove `AIConfig` and `ai_config`.
- `.env.example`: remove the AWS, Bedrock and `AI_REQUEST_TIMEOUT` lines and the `APP_EXTRA=ai`
  example.
- `pyproject.toml`: remove the `ai` extra. Then run `uv lock` and `just setup`.
- `.github/workflows/ci.yml`: remove `ai` from the matrix. Run the type check in the `workers`
  variant, because pyright needs all modules installed.
- `tests/conftest.py`: remove the `pydantic_ai` block. Pyright cannot resolve its import
  without the package.
- `AGENTS.md` and `README.md`: remove Pydantic AI and the `ai` extra.

`app/integrations/sentry/client.py` and the route inventory test check
`find_spec("pydantic_ai")`. Without the package, these checks do nothing.

Keep the `workers` extra also when the project has no task yet. The core installs and runs
without it.

## 4. Remove the template files

```bash
git rm -q docs/review.md .agents/references/new-project.md
```

Remove the line of this file from the references in `AGENTS.md`. Run `just ci`.

## 5. Add the first feature

Follow "Add a feature" in `AGENTS.md`. Add authentication before the first route that must not
be public: read `.agents/references/auth-and-tenancy.md`.
