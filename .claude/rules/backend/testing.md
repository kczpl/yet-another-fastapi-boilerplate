---
paths:
  - "tests/**/*.py"
---

# Python Testing Patterns

Testing conventions for the FastAPI backend.

## Core Principles

- All tests are async via `pytest-asyncio` (`asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` needed)
- Test against a real PostgreSQL database (not mocks for DB operations)
- Mock interactions with 3rd-party services (email, external APIs, LLMs)
- Each test runs in a transaction that is rolled back afterwards (isolation via `db_session`)
- Use `factory_boy` factories to create test data
- Never enqueue real Celery tasks — use the `mock_celery` fixture

## Test Structure

```
tests/
├── conftest.py           # engine, db_session, client, mock_celery, factory auto-registration
├── factories/            # factory definitions (auto-discovered)
│   ├── base.py           # BaseFactory with async create()
│   └── {domain}.py       # domain factories
├── core/                 # core module tests
├── features/             # feature service + route tests (mirrors app/features/)
│   └── {domain}/service/
└── repositories/         # data layer tests (crud)
```

**Test structure mirrors source structure:**

- `app/features/items/service/create.py` → `tests/features/items/service/test_create.py`
- `app/repositories/items/crud.py` → `tests/repositories/items/test_crud.py`

## Running Tests

```bash
docker compose up postgres-test -d   # start the test database
uv run pytest                          # or: just test
uv run pytest tests/features/items -v  # a subset
```

## Factories

Async factories integrate with the SQLAlchemy async session:

```python
class ItemFactory(BaseFactory, metaclass=BaseMetaFactory[Item]):
    class Meta:
        model = Item

    id = LazyFunction(uuid7)
    name = Sequence(lambda n: f"Item {n}")
    created_at = LazyFunction(utc_now)
```

**Auto-registration:** `conftest.py` walks `tests/factories/` and imports every module, then binds the session to each `BaseFactory` subclass per test. New factories are picked up automatically.

**Deriving FKs from related objects** — declare it on the factory instead of overriding `create()`:

```python
class ItemNoteFactory(BaseFactory, metaclass=BaseMetaFactory[ItemNote]):
    item = SubFactory(ItemFactory)
    _derive_fks: ClassVar = {"item": {"item_id": "id"}}
```

Semantics: `{related_kwarg: {fk_field: attr_on_related}}` — when the related object is passed and the FK kwarg is absent, the FK is filled from the related object.

## Service Tests

Test service classes directly without the HTTP layer — instantiate with `db_session`.

```python
class TestCreateItemService:
    async def test_create_item_persists(self, db_session: AsyncSession):
        result = await CreateItemService(db=db_session).call(name="Widget")

        item = (await db_session.execute(select(Item).where(Item.name == "Widget"))).scalar_one()
        assert item.status == "active"
```

Assertions:
- Use `db_session.execute(select(...))` to verify state changes
- Use `pytest.raises(APIException)` and check `exc_info.value.status_code` / `error_key`
- Don't assert on response messages here (that's for route tests)

### `_setup()` helpers

When several tests need the same multi-entity prerequisites, add a `_setup()` method on the test class (or a module-level `async def _setup(db_session, ...)` when shared across classes) that builds and returns the entities. Accept `**overrides` to customize per test.

## Route Tests

Use the `client` fixture (overrides the DB dependency, includes `mock_celery`):

```python
class TestItemRoutes:
    async def test_summarize_enqueues_task(self, client: AsyncClient, mock_celery):
        item = await ItemFactory.create()
        resp = await client.post(f"/api/v1/items/{item.id}/summarize")
        assert resp.status_code == 202
        mock_celery.assert_called_once_with(str(item.id))
```

## Test Naming

- `test_{action}_with_{condition}` — e.g. `test_create_item_with_blank_name`
- `test_{action}_{expected_outcome}` — e.g. `test_get_item_not_found`

Cover: the valid case, invalid input, and edge cases (empty, already-done, conflict).

## AI Agent Tests

Don't hit a real LLM in normal CI. Two layers:

1. **Output / validator unit tests** — construct the agent's output model with plain data and assert the `@model_validator` / `_check_*` helpers behave (normalization, `requires_review` on final retry). Fast, no DB, no model.
2. **Service tests** — patch the async wrapper so the service runs without a model:

```python
@patch("app.features.items.service.summarize.summarize_text")
async def test_summarize_stores_summary(mock_summarize, db_session):
    mock_summarize.return_value = TextSummary(title="t", summary="s", keywords=["k"])
    item = await ItemFactory.create(description="long text", summary=None)
    await SummarizeItemService(db=db_session).call(str(item.id))
    assert item.summary == "s"
```

Real-LLM integration tests (if you add them) should be env-gated (e.g. `RUN_AGENT_TEST=1`) so they never run in default CI.
