"""Generic async repository.

Encapsulates data access so services never touch SQLAlchemy directly. Uses
``flush`` (not ``commit``) so multiple repository calls can participate in one
transaction managed by the ``get_db`` dependency.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Common CRUD operations for a single model."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, obj_id: str) -> ModelT | None:
        return await self.session.get(self.model, obj_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[ModelT]:
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()
