"""
健康检查端点单元测试。
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.server import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """验证 /health 端点返回正确的健康状态。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "dry_run" in data
    assert "app_env" in data


@pytest.mark.asyncio
async def test_health_dry_run_default_true() -> None:
    """验证默认情况下 dry_run 为 True。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    data = response.json()
    assert data["dry_run"] is True
