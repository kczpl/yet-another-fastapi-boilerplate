---
paths:
  - "app/**/*.py"
---

## FastAPI Best Practices

### Async handling

- Use `async def` for routes with I/O operations (database, external APIs, file operations)
- Use `def` for CPU-bound operations or when calling blocking libraries (FastAPI runs them in a threadpool)
- Never block the event loop - use `run_in_threadpool` for sync libraries if necessary
- Prefer async libraries: `httpx.AsyncClient` over `requests`

### Dependency Injection

- Chain dependencies to avoid code duplication and enable reuse
- Use dependencies for validation - validate data against database constraints, check existence
- Keep dependencies focused - each should validate one concern
- Remember caching - FastAPI caches a dependency's result within a request scope, so a chained dependency runs once even if several others depend on it
- Prefer async dependencies to avoid unnecessary thread-pool usage

### Response handling

- Never return Pydantic models directly - let FastAPI serialize via `response_model`. Returning a model makes FastAPI build it twice (once by you, once validating the response).
- Use `response_model` to define clear API contracts; set `status_code`, `summary`, `description`
- Services return plain `dict`s; the route's `response_model` validates them

```python
@router.post("/items", response_model=APIResponse[ItemResponse], status_code=status.HTTP_201_CREATED)
async def create_item(body: ItemCreate, service: CreateItemService = Depends()) -> dict:
    return await service.call(name=body.name, description=body.description)
```

### Pydantic Usage

- Use Pydantic V2; leverage validators for complex validation
- Use custom base models for global configuration (datetime serialization, etc.) when needed
- Decouple settings - split `BaseSettings` across domains rather than one monolithic config (see `app/core/config.py`)
- Don't overuse Pydantic: in FastAPI use it for request/response models, not for internal data passing — services pass plain dicts/dataclasses
- A `ValueError` raised in a schema validator surfaces to the client as a 422 with details

## API Layer

Routes handle authorization and orchestrate services. Routes live inside each feature's `routes/` directory and are aggregated in `app/api/__init__.py`.

**Rule:** routers carry no prefix; use full paths in every decorator (never `""` or a trailing `/`). The version prefix is applied once during aggregation.

```python
# app/api/__init__.py — aggregates feature routers under /api/v1
from fastapi import APIRouter
from app.features.items.routes import items

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(items.router)
```

```python
# app/features/items/routes/items.py
router = APIRouter(tags=["items"])

@router.get("/items/{item_id}", response_model=APIResponse[ItemResponse])
async def get_item(item: ValidItem) -> dict:
    return {"data": serialize_item(item)}
```

> When you add authentication, keep role checks and auth in the dependency layer (e.g. a `CurrentUser` dependency in `app/repositories/auth/dependencies.py`) and chain access dependencies on top of it — never inside services.

## Dependencies as Validation

Pydantic validates shapes; dependencies validate against the database and load the entity. This removes repeated existence checks from every endpoint.

```python
# app/repositories/items/dependencies.py
async def valid_item_id(item_id: UUID, db: AsyncDb) -> Item:
    item = await crud.get_item_by_id(db, item_id)
    if item is None:
        raise_not_found("item_not_found")
    return item

ValidItem = Annotated[Item, Depends(valid_item_id)]
```

### Chain dependencies

Build higher-level dependencies on top of smaller ones; results are cached per request, so the shared link runs once.

```python
async def valid_owned_item(item: ValidItem, user: CurrentUser) -> Item:
    if item.owner_id != user.id:
        raise_forbidden("not_item_owner")
    return item
```

Use the **same path variable name** across endpoints so dependencies chain cleanly (`/items/{item_id}`, `/items/{item_id}/notes`).

## Pagination

Offset/limit pagination with a consistent response shape. Use the `pagination_params` dependency factory from `app/core/pagination.py`.

```python
@router.get("/items", response_model=APIResponse[ItemListResponse])
async def list_items(
    pagination: Pagination = Depends(pagination_params()),
    service: ListItemsService = Depends(),
) -> dict:
    return await service.call(page=pagination.page, page_size=pagination.page_size)
```

Service response — always these 5 fields:

```python
return {
    "items": [...],
    "page": page,
    "page_size": page_size,
    "total_count": total_count,
    "total_pages": math.ceil(total_count / page_size) if total_count > 0 else 0,
}
```

Get `total_count` in the same query with a window function (`func.count().over()`) — no second round-trip. Defaults: `page=1`, `page_size=10`, max `page_size=100`.

## File Uploads (when needed)

Accept `list[UploadFile]` via multipart/form-data. Validate before reading full content where possible: MIME type → `Content-Length` header → read bytes → actual byte size. Add the route prefix to `LARGE_BODY_PATHS` in `app/core/security.py` so the size-limit middleware allows the larger body.
