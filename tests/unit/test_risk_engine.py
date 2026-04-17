"""
Risk Engine 服务单元测试。
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from apps.risk_engine.service import RiskEngineService
 

class TestRiskEngineService:
    """RiskEngineService 测试。"""

    @pytest.mark.asyncio
    async def test_normal_order_passes(self) -> None:
        """正常小额订单应通过风控。"""
        mock_session = MagicMock()
        service = RiskEngineService(mock_session)
        payload = {
            "market_name": "polymarket",
            "current_market_risk_usd": 100.0,
            "current_theme_risk_usd": 200.0,
            "daily_new_risk_usd": 100.0,
            "daily_loss_usd": 0.0,
            "orderbook_depth_usd": 500.0,
            "spread_pct": 0.01,
            "estimated_slippage_pct": 0.01,
            "expected_hold_minutes": 60,
            "hours_to_expiry": 48.0,
            "order_risk_usd": 50.0,
        }
        result = await service.check(uuid.uuid4(), payload)
        assert result.allow is True
        assert result.reason_codes == []

    @pytest.mark.asyncio
    async def test_oversized_order_fails(self) -> None:
        """超过单笔限额应被拒绝。"""
        mock_session = MagicMock()
        service = RiskEngineService(mock_session)
        payload = {
            "market_name": "polymarket",
            "current_market_risk_usd": 990.0,
            "current_theme_risk_usd": 2990.0,
            "daily_new_risk_usd": 4990.0,
            "daily_loss_usd": 0.0,
            "orderbook_depth_usd": 500.0,
            "spread_pct": 0.01,
            "estimated_slippage_pct": 0.01,
            "expected_hold_minutes": 60,
            "hours_to_expiry": 48.0,
            "order_risk_usd": 50.0,
        }
        result = await service.check(uuid.uuid4(), payload)
        assert result.allow is False
        assert any("exceeds limit" in reason for reason in result.reason_codes)

    def test_get_current_limits(self) -> None:
        """应能返回当前风控限额。"""
        mock_session = MagicMock()
        service = RiskEngineService(mock_session)
        limits = service.get_current_limits()
        assert "allowed_markets" in limits
        assert "near_expiry_hours_limit" in limits
