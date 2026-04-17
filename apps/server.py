"""
Polymarket 事件驱动候选单系统 —— FastAPI 主应用入口。

功能：
- 注册所有子模块路由
- 提供全局健康检查
- 管理应用生命周期（数据库/适配器初始化与清理）
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from libs.models.schemas import HealthResponse
from libs.models.settings import get_settings
from libs.utils.logging import setup_logging

# ---------- 子模块路由导入 ----------
from apps.ingestor.main import router as ingestor_router
from apps.mapper.main import router as mapper_router
from apps.rules.main import router as rules_router
from apps.thesis.main import router as thesis_router
from apps.risk_engine.main import router as risk_engine_router
from apps.sizing.main import router as sizing_router
from apps.execution.main import router as execution_router
from apps.monitor.main import router as monitor_router
from apps.reporting.main import router as reporting_router
from apps.orchestrator.main import router as orchestrator_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理：启动时初始化，关闭时清理。"""
    # ---- startup ----
    setup_logging()
    # TODO: 预热数据库连接池、初始化适配器等
    yield
    # ---- shutdown ----
    # TODO: 关闭数据库引擎、清理适配器连接


def create_app() -> FastAPI:
    """应用工厂函数。"""
    settings = get_settings()

    app = FastAPI(
        title="Polymarket 事件驱动候选单系统",
        description="研究 / 候选单 / 风控 / 仓位管理 / 执行 / 监控 / 报告",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ---------- 中间件 ----------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------- 健康检查 ----------
    @app.get("/health", response_model=HealthResponse, tags=["系统"])
    async def health_check() -> HealthResponse:
        """全局健康检查端点。"""
        return HealthResponse(
            status="ok",
            version="0.1.0",
            app_env=settings.app_env,
            dry_run=settings.dry_run,
        )

    # ---------- 注册子路由 ----------
    app.include_router(ingestor_router)
    app.include_router(mapper_router)
    app.include_router(rules_router)
    app.include_router(thesis_router)
    app.include_router(risk_engine_router)
    app.include_router(sizing_router)
    app.include_router(execution_router)
    app.include_router(monitor_router)
    app.include_router(reporting_router)
    app.include_router(orchestrator_router)

    return app


# uvicorn 入口
app = create_app()
