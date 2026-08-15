import uuid

from httpx import AsyncClient


async def test_create_project(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/projects", json={"name": "RAG Eval", "description": "Comparing retrievers"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "RAG Eval"
    assert body["description"] == "Comparing retrievers"
    assert uuid.UUID(body["id"])
    assert body["created_at"]
    assert body["updated_at"]


async def test_create_project_without_description(client: AsyncClient) -> None:
    response = await client.post("/api/v1/projects", json={"name": "No description"})

    assert response.status_code == 201
    assert response.json()["description"] is None


async def test_create_project_requires_a_name(client: AsyncClient) -> None:
    response = await client.post("/api/v1/projects", json={"name": ""})

    assert response.status_code == 422


async def test_list_projects_returns_created_projects(client: AsyncClient) -> None:
    await client.post("/api/v1/projects", json={"name": "Project A"})
    await client.post("/api/v1/projects", json={"name": "Project B"})

    response = await client.get("/api/v1/projects")

    assert response.status_code == 200
    names = {project["name"] for project in response.json()}
    assert {"Project A", "Project B"} <= names


async def test_get_project_by_id(client: AsyncClient) -> None:
    created = await client.post("/api/v1/projects", json={"name": "Fetch me"})
    project_id = created.json()["id"]

    response = await client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["id"] == project_id


async def test_get_project_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/projects/{uuid.uuid4()}")

    assert response.status_code == 404
