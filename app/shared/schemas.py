from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel


T = TypeVar("T")


class Pagination(BaseModel):
    limit: int = Field(20, ge=1)
    offset: int = Field(0, ge=0)


class PaginatedResponse(GenericModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


