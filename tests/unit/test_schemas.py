"""
Pydantic Schema 单元测试。
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from libs.models.schemas import (
    CandidateOrderCreate,
    HealthResponse,
    RiskDecision,
    SizingDecision,
)


class TestHealthResponse:
    """HealthResponse Schema 测试。"""

    def test_defaults(self) -> None:
        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.dry_run is True

    def test_custom_values(self) -> None:
        resp = HealthResponse(status="degraded", app_env="production", dry_run=False)
        assert resp.status == "degraded"
        assert resp.dry_run is False


class TestCandidateOrderCreate:
    """CandidateOrderCreate Schema 测试。"""

    def test_valid_order(self) -> None:
        order = CandidateOrderCreate(
            market_event_id=uuid.uuid4(),
            side="BUY",
            outcome="YES",
            target_price=0.65,
            size=100,
        )
        assert order.side == "BUY"
        assert order.outcome == "YES"

    def test_invalid_side(self) -> None:
        with pytest.raises(ValidationError):
            CandidateOrderCreate(
                market_event_id=uuid.uuid4(),
                side="INVALID",
                outcome="YES",
                target_price=0.5,
                size=10,
            )

    def test_invalid_outcome(self) -> None:
        with pytest.raises(ValidationError):
            CandidateOrderCreate(
                market_event_id=uuid.uuid4(),
                side="BUY",
                outcome="MAYBE",
                target_price=0.5,
                size=10,
            )

    def test_price_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            CandidateOrderCreate(
                market_event_id=uuid.uuid4(),
                side="BUY",
                outcome="YES",
                target_price=1.5,  # 超出 (0, 1] 范围
                size=10,
            )

    def test_negative_size(self) -> None:
        with pytest.raises(ValidationError):
            CandidateOrderCreate(
                market_event_id=uuid.uuid4(),
                side="BUY",
                outcome="YES",
                target_price=0.5,
                size=-10,
            )


class TestRiskDecision:
    """RiskDecision Schema 测试。"""

    def test_passed(self) -> None:
        result = RiskDecision(allow=True)
        assert result.allow is True
        assert result.reason_codes == []
        assert result.risk_metrics_json == {}

    def test_failed_with_reasons(self) -> None:
        result = RiskDecision(
            allow=False,
            reason_codes=["超过单笔限额", "频率过高"],
            risk_metrics_json={"spread": 0.08},
        )
        assert result.allow is False
        assert len(result.reason_codes) == 2


class TestSizingDecision:
    """SizingDecision Schema 测试。"""

    def test_defaults(self) -> None:
        result = SizingDecision(
            candidate_id=uuid.uuid4(),
            p_market=0.45,
            q_raw=0.60,
            alpha=0.5,
            q_adj=0.525,
            taker_fee_per_share=0.01,
            expected_slippage_per_share=0.01,
            exit_cost_reserve=0.01,
            uncertainty_haircut=0.02,
            p_eff=0.49,
            edge_net=0.035,
            f_full=0.068627,
            f_half=0.034313,
            f_final=0.034313,
        )
        assert result.sizing_reason_codes == []
        assert result.f_final == pytest.approx(0.034313)
