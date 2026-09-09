from importlib.util import find_spec

import pytest
from httpx import AsyncClient

from tests.factories.item import ItemFactory


class TestItemRoutes:
    async def test_create_item(self, client: AsyncClient):
        resp = await client.post("/api/v1/items", json={"name": "Gadget"})

        assert resp.status_code == 201
        body = resp.json()
        assert body["message"] == "api.general.created"
        assert body["data"]["name"] == "Gadget"
        assert body["data"]["status"] == "active"

    async def test_create_item_with_blank_name(self, client: AsyncClient):
        resp = await client.post("/api/v1/items", json={"name": ""})

        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "api.general.validation_error"
        assert body["data"]["details"][0]["field"] == "body.name"

    async def test_list_items_paginates(self, client: AsyncClient):
        for _ in range(3):
            await ItemFactory.create()

        resp = await client.get("/api/v1/items", params={"page": 2, "page_size": 2})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_count"] == 3
        assert data["total_pages"] == 2
        assert len(data["items"]) == 1

    async def test_list_items_with_page_size_over_limit(self, client: AsyncClient):
        resp = await client.get("/api/v1/items", params={"page_size": 101})

        assert resp.status_code == 422

    async def test_get_item(self, client: AsyncClient):
        item = await ItemFactory.create(name="Findable")

        resp = await client.get(f"/api/v1/items/{item.id}")

        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Findable"

    async def test_get_item_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/items/00000000-0000-0000-0000-000000000000")

        assert resp.status_code == 404
        assert resp.json()["error"] == "api.items.item_not_found"

    @pytest.mark.skipif(find_spec("pydantic_ai") is None, reason="requires the ai extra")
    async def test_summarize_enqueues_task(self, client: AsyncClient, mock_celery):
        item = await ItemFactory.create()

        resp = await client.post(f"/api/v1/items/{item.id}/summarize")

        assert resp.status_code == 202
        mock_celery.assert_called_once_with((str(item.id),), {})

    @pytest.mark.parametrize("name", [" ", "\t\n"])
    async def test_whitespace_name_is_rejected(self, client: AsyncClient, name: str):
        response = await client.post("/api/v1/items", json={"name": name})
        assert response.status_code == 422

    async def test_item_name_is_trimmed(self, client: AsyncClient):
        response = await client.post("/api/v1/items", json={"name": "  Widget  "})
        assert response.json()["data"]["name"] == "Widget"

    async def test_out_of_range_page_preserves_metadata(self, client: AsyncClient):
        await ItemFactory.create()
        response = await client.get("/api/v1/items", params={"page": 10})
        assert response.status_code == 200
        assert response.json()["data"] == {"items": [], "page": 10, "page_size": 10, "total_count": 1, "total_pages": 1}
