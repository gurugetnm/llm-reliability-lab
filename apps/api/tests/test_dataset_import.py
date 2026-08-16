"""Tests for JSON/JSONL dataset bulk import — both the parser
(`dataset_service.parse_import_content`) directly, and the
`/api/v1/datasets/{id}/import` route end to end.
"""

import json

import pytest
from app.core.exceptions import ValidationError
from app.models.project import Project
from app.schemas.dataset import DatasetCreate, DatasetItemCreate
from app.services import dataset_service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# --- parser --------------------------------------------------------------


def test_parse_json_import_accepts_a_valid_array() -> None:
    content = json.dumps(
        [
            {"input": "What is TCP?", "expected_output": "A transport protocol"},
            {"input": "What is DNS?"},
        ]
    )

    parsed = dataset_service.parse_import_content(content, "json")

    assert parsed.errors == []
    assert len(parsed.rows) == 2
    assert parsed.rows[0]["input"] == "What is TCP?"


def test_parse_jsonl_import_accepts_valid_lines_and_skips_blanks() -> None:
    content = '{"input": "What is TCP?"}\n\n{"input": "What is DNS?"}\n'

    parsed = dataset_service.parse_import_content(content, "jsonl")

    assert parsed.errors == []
    assert len(parsed.rows) == 2


def test_parse_json_import_reports_missing_input_field_with_line_number() -> None:
    content = json.dumps(
        [
            {"input": "ok"},
            {"expected_output": "no input here"},
        ]
    )

    parsed = dataset_service.parse_import_content(content, "json")

    assert len(parsed.rows) == 1
    assert len(parsed.errors) == 1
    assert parsed.errors[0].line == 2
    assert "missing required field: input" in parsed.errors[0].message


def test_parse_jsonl_import_reports_invalid_json_with_line_number() -> None:
    content = '{"input": "ok"}\nnot json\n{"input": "also ok"}'

    parsed = dataset_service.parse_import_content(content, "jsonl")

    assert len(parsed.rows) == 2
    assert len(parsed.errors) == 1
    assert parsed.errors[0].line == 2


def test_parse_json_import_rejects_non_array_top_level() -> None:
    with pytest.raises(ValidationError):
        dataset_service.parse_import_content(json.dumps({"input": "ok"}), "json")


def test_parse_json_import_rejects_malformed_json() -> None:
    with pytest.raises(ValidationError):
        dataset_service.parse_import_content("{not valid json", "json")


async def test_bulk_import_bumps_dataset_version_and_appends_positions(
    db_session: AsyncSession,
) -> None:
    project = Project(name="Import test project")
    db_session.add(project)
    await db_session.flush()
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Import target")
    )
    await dataset_service.create_dataset_item(
        db_session, dataset.id, DatasetItemCreate(input="first")
    )

    content = json.dumps([{"input": "second"}, {"input": "third"}])
    updated, imported_count = await dataset_service.bulk_import_dataset_items(
        db_session, dataset.id, content=content, fmt="json"
    )

    assert imported_count == 2
    assert updated.version == 2
    items, total = await dataset_service.list_dataset_items(
        db_session, dataset.id, page=1, page_size=10
    )
    assert total == 3
    assert [item.position for item in items] == [0, 1, 2]


async def test_bulk_import_rejects_the_whole_batch_if_any_record_is_invalid(
    db_session: AsyncSession,
) -> None:
    project = Project(name="Import rejection test project")
    db_session.add(project)
    await db_session.flush()
    dataset = await dataset_service.create_dataset(
        db_session, DatasetCreate(project_id=project.id, name="Reject target")
    )

    content = json.dumps([{"input": "good"}, {"expected_output": "missing input"}])
    with pytest.raises(ValidationError):
        await dataset_service.bulk_import_dataset_items(
            db_session, dataset.id, content=content, fmt="json"
        )

    _, total = await dataset_service.list_dataset_items(
        db_session, dataset.id, page=1, page_size=10
    )
    assert total == 0  # nothing was imported — not even the valid record


# --- route -----------------------------------------------------------------


async def test_import_json_via_api(client: AsyncClient) -> None:
    project = await client.post("/api/v1/projects", json={"name": "Import API test"})
    dataset = await client.post(
        "/api/v1/datasets",
        json={"project_id": project.json()["id"], "name": "Imported"},
    )
    dataset_id = dataset.json()["id"]

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/import",
        json={
            "format": "json",
            "content": json.dumps([{"input": "What is TCP?"}, {"input": "What is DNS?"}]),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["dataset"]["item_count"] == 2
    assert body["dataset"]["version"] == 2


async def test_import_jsonl_via_api(client: AsyncClient) -> None:
    project = await client.post("/api/v1/projects", json={"name": "Import API JSONL test"})
    dataset = await client.post(
        "/api/v1/datasets",
        json={"project_id": project.json()["id"], "name": "Imported JSONL"},
    )
    dataset_id = dataset.json()["id"]

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/import",
        json={"format": "jsonl", "content": '{"input": "a"}\n{"input": "b"}'},
    )

    assert response.status_code == 200
    assert response.json()["imported_count"] == 2


async def test_import_with_invalid_records_returns_422_with_line_numbers(
    client: AsyncClient,
) -> None:
    project = await client.post("/api/v1/projects", json={"name": "Import API error test"})
    dataset = await client.post(
        "/api/v1/datasets",
        json={"project_id": project.json()["id"], "name": "Invalid import"},
    )
    dataset_id = dataset.json()["id"]

    content = "\n".join(['{"input": "ok"}'] * 16 + ['{"expected_output": "no input"}'])
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/import", json={"format": "jsonl", "content": content}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["errors"][0]["line"] == 17
    assert "missing required field: input" in body["errors"][0]["message"]
