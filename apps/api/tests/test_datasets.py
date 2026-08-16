"""Route-level tests for `/api/v1/datasets` — request validation, status
codes, and response shape. Business-rule coverage lives in
`test_dataset_service.py`; these are about the HTTP layer on top of it.
"""

import uuid

from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", json={"name": "Dataset API test project"})
    return response.json()["id"]


async def test_create_dataset(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    response = await client.post(
        "/api/v1/datasets",
        json={"project_id": project_id, "name": "Q&A set", "description": "A test set"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Q&A set"
    assert body["version"] == 1
    assert body["item_count"] == 0


async def test_create_dataset_for_missing_project_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/datasets", json={"project_id": str(uuid.uuid4()), "name": "Orphan"}
    )
    assert response.status_code == 404


async def test_create_dataset_rejects_empty_name(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    response = await client.post("/api/v1/datasets", json={"project_id": project_id, "name": ""})
    assert response.status_code == 422


async def test_list_datasets_filters_by_project(client: AsyncClient) -> None:
    project_a = await _create_project(client)
    project_b = await _create_project(client)
    await client.post("/api/v1/datasets", json={"project_id": project_a, "name": "A"})
    await client.post("/api/v1/datasets", json={"project_id": project_b, "name": "B"})

    response = await client.get("/api/v1/datasets", params={"project_id": project_a})

    assert response.status_code == 200
    names = [d["name"] for d in response.json()]
    assert names == ["A"]


async def test_get_dataset_returns_404_when_missing(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/datasets/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_update_dataset(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    created = await client.post("/api/v1/datasets", json={"project_id": project_id, "name": "Old"})
    dataset_id = created.json()["id"]

    response = await client.patch(f"/api/v1/datasets/{dataset_id}", json={"name": "New"})

    assert response.status_code == 200
    assert response.json()["name"] == "New"


async def test_delete_dataset(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    created = await client.post("/api/v1/datasets", json={"project_id": project_id, "name": "Temp"})
    dataset_id = created.json()["id"]

    response = await client.delete(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 204

    follow_up = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert follow_up.status_code == 404


# --- dataset items -----------------------------------------------------


async def _create_dataset(client: AsyncClient) -> str:
    project_id = await _create_project(client)
    created = await client.post(
        "/api/v1/datasets", json={"project_id": project_id, "name": "Items test"}
    )
    return created.json()["id"]


async def test_create_dataset_item(client: AsyncClient) -> None:
    dataset_id = await _create_dataset(client)

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/items",
        json={"input": "What is TCP?", "expected_output": "A transport protocol"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["input"] == "What is TCP?"
    assert body["position"] == 0


async def test_create_dataset_item_for_missing_dataset_returns_404(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/datasets/{uuid.uuid4()}/items", json={"input": "x"})
    assert response.status_code == 404


async def test_list_dataset_items_is_paginated(client: AsyncClient) -> None:
    dataset_id = await _create_dataset(client)
    for i in range(3):
        await client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": f"item-{i}"})

    response = await client.get(
        f"/api/v1/datasets/{dataset_id}/items", params={"page": 1, "page_size": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


async def test_list_dataset_items_rejects_oversized_page_size(client: AsyncClient) -> None:
    dataset_id = await _create_dataset(client)
    response = await client.get(f"/api/v1/datasets/{dataset_id}/items", params={"page_size": 1000})
    assert response.status_code == 422


async def test_update_dataset_item(client: AsyncClient) -> None:
    dataset_id = await _create_dataset(client)
    created = await client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": "old"})
    item_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/datasets/{dataset_id}/items/{item_id}", json={"input": "new"}
    )

    assert response.status_code == 200
    assert response.json()["input"] == "new"


async def test_update_dataset_item_for_wrong_dataset_returns_404(client: AsyncClient) -> None:
    dataset_id = await _create_dataset(client)
    other_dataset_id = await _create_dataset(client)
    created = await client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": "q"})
    item_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/datasets/{other_dataset_id}/items/{item_id}", json={"input": "new"}
    )

    assert response.status_code == 404


async def test_delete_dataset_item(client: AsyncClient) -> None:
    dataset_id = await _create_dataset(client)
    created = await client.post(f"/api/v1/datasets/{dataset_id}/items", json={"input": "q"})
    item_id = created.json()["id"]

    response = await client.delete(f"/api/v1/datasets/{dataset_id}/items/{item_id}")
    assert response.status_code == 204

    listing = await client.get(f"/api/v1/datasets/{dataset_id}/items")
    assert listing.json()["total"] == 0
