from httpx import AsyncClient

from tests.factories.item import ItemFactory


class TestItemRoutes:
    async def test_create_item(self, client: AsyncClient):
        resp = await client.post("/api/v1/items", json={"name": "Gadget"})

        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["name"] == "Gadget"

    async def test_get_item_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/items/00000000-0000-0000-0000-000000000000")

        assert resp.status_code == 404
        assert resp.json()["error"] == "item_not_found"

    async def test_summarize_enqueues_task(self, client: AsyncClient, mock_celery):
        item = await ItemFactory.create()

        resp = await client.post(f"/api/v1/items/{item.id}/summarize")

        assert resp.status_code == 202
        mock_celery.assert_called_once_with(str(item.id))
