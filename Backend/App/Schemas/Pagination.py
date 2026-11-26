"""Paged list envelope (archive §9.1): data array + pagination block + meta."""

import math
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from Backend.App.Schemas.Common import Meta

ItemT = TypeVar("ItemT")

MAX_PAGE_SIZE = 100


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def build(cls, *, page: int, page_size: int, total_items: int) -> "PaginationInfo":
        total_pages = math.ceil(total_items / page_size) if total_items else 0
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class PaginatedEnvelope(BaseModel, Generic[ItemT]):
    success: Literal[True] = True
    message: str
    data: list[ItemT]
    pagination: PaginationInfo
    meta: Meta = Field(default_factory=Meta)


def paginated(items: list[ItemT], message: str, *, page: int, page_size: int, total_items: int) -> PaginatedEnvelope[ItemT]:
    return PaginatedEnvelope[ItemT](
        message=message,
        data=items,
        pagination=PaginationInfo.build(page=page, page_size=page_size, total_items=total_items),
    )
