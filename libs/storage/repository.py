"""
通用仓储层基类。

提供 CRUD 泛型操作，各业务模块可继承并扩展。
"""

from __future__ import annotations

import uuid
from typing import Generic, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """异步通用仓储，封装常见 CRUD。"""

    def __init__(self, session: AsyncSession, model_class: Type[ModelT]) -> None:
        self._session = session
        self._model_class = model_class

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT | None:
        """按主键查询。"""
        return await self._session.get(self._model_class, record_id)

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        """分页列表查询。"""
        stmt = (
            select(self._model_class)
            .order_by(self._model_class.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, instance: ModelT) -> ModelT:
        """插入新记录。"""
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update(self, instance: ModelT) -> ModelT:
        """更新已有记录（确保 instance 在 session 中）。"""
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """删除记录。"""
        await self._session.delete(instance)
        await self._session.flush()
