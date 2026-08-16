"""Generic pagination — shared by dataset items, experiments, runs, and
run items so every list endpoint that could grow unbounded (a dataset
with thousands of items, a run with thousands of items) paginates the
same way instead of each endpoint inventing its own shape.
"""

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

#: Keeps a single accidental "list everything" request from loading
#: thousands of rows (and their JSONB payloads) into one response.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):  # noqa: UP046 — PEP 695 needs Python 3.12+, api supports 3.11+
    """A single page of results plus enough metadata to render pagination
    controls and fetch the next page."""

    items: list[ItemT]
    page: int
    page_size: int
    total: int


PageParam = Annotated[int, Query(ge=1, description="1-indexed page number")]
PageSizeParam = Annotated[
    int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page (max 100)")
]


def offset_for(page: int, page_size: int) -> int:
    return (page - 1) * page_size
