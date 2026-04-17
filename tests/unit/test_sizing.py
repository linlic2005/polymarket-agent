"""
Sizing 服务单元测试。
"""

from __future__ import annotations

import uuid

from apps.sizing.service import SizingService


class TestSizingService:
    """SizingService 测试。"""

    def test_net_edge_positive_generates_fraction(self) -> None:
        service = SizingService()
        result = service.calculate(
            candidate_id=uuid.uuid4(),
            p_market=0.45,
            q_raw=0.60,
            bankroll_override=10_000.0,
        )

        assert result.edge_net > 0
        assert result.f_final > 0
        assert result.f_final <= result.f_half

    def test_non_positive_net_edge_returns_zero_position(self) -> None:
        service = SizingService()
        result = service.calculate(
            candidate_id=uuid.uuid4(),
            p_market=0.50,
            q_raw=0.50,
            bankroll_override=10_000.0,
        )

        assert result.edge_net <= 0
        assert result.f_full == 0
        assert result.f_half == 0
        assert result.f_final == 0
        assert "Net edge is zero or negative." in result.sizing_reason_codes

    def test_position_is_capped_by_bankroll_limit(self) -> None:
        service = SizingService()
        result = service.calculate(
            candidate_id=uuid.uuid4(),
            p_market=0.10,
            q_raw=0.95,
            bankroll_override=100_000.0,
        )

        assert result.f_final == 0.005
        assert any("Position capped by max limit" in reason for reason in result.sizing_reason_codes)
