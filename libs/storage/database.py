"""
数据库引擎 & 会话管理。

提供异步 (async) 和同步 (sync) 两套引擎：
- 异步引擎用于 FastAPI 请求处理
- 同步引擎用于 Alembic 迁移
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from libs.models.settings import get_settings

# ------------------------------------------------------------------ #
# 异步引擎（FastAPI / 业务逻辑）
# ------------------------------------------------------------------ #
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """获取全局异步数据库引擎（懒初始化）。"""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            echo=(settings.app_env == "development"),
            pool_size=10,
            max_overflow=20,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取异步会话工厂。"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """异步上下文管理器，自动提交 / 回滚。"""
    factory = get_async_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def async_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 用的异步会话生成器。"""
    async with get_async_session() as session:
        yield session


# ------------------------------------------------------------------ #
# 同步引擎（Alembic / 脚本）
# ------------------------------------------------------------------ #
def get_sync_engine():
    """获取同步引擎，主要用于 Alembic 迁移。"""
    settings = get_settings()
    return create_engine(
        settings.database_url_sync,
        echo=(settings.app_env == "development"),
    )


def get_sync_session_factory() -> sessionmaker[Session]:
    """获取同步会话工厂。"""
    return sessionmaker(bind=get_sync_engine())
