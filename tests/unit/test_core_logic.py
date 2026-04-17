import uuid
import pytest

from apps.sizing.service import SizingService
from apps.risk_engine.service import RiskEngineService

class MockSession:
    pass

@pytest.fixture
def sizing_service():
    service = SizingService()
    service._config = {
        "alpha": 0.5,
        "max_position_size_usd": 500.0,
        "taker_fee_per_share": 0.01,
        "expected_slippage_per_share": 0.01,
        "exit_cost_reserve": 0.01,
        "uncertainty_haircut": 0.02,
        "bankroll_usd": 10000.0
    }
    return service

@pytest.fixture
def risk_service():
    service = RiskEngineService(MockSession())
    service._limits = {
        "allowed_markets": ["polymarket"],
        "max_risk_per_market_usd": 1000.0,
        "max_risk_per_theme_usd": 3000.0,
        "max_daily_new_risk_usd": 5000.0,
        "max_daily_loss_usd": 500.0,
        "min_orderbook_depth_usd": 100.0,
        "max_spread_pct": 0.10,
        "max_estimated_slippage_pct": 0.05,
        "max_hold_minutes": 10080,
        "near_expiry_hours_limit": 24
    }
    return service

def test_sizing_edge_net_le_zero(sizing_service):
    """Sizing: edge_net <= 0 拒绝下单"""
    res = sizing_service.calculate(uuid.uuid4(), p_market=0.5, q_raw=0.5)
    assert res.edge_net < 0
    assert res.f_final == 0.0
    assert "Net edge is zero or negative." in res.sizing_reason_codes

def test_sizing_half_kelly(sizing_service):
    """Sizing: half kelly 公式推导是否精确一致"""
    sizing_service._config["max_position_size_usd"] = 10000.0 # avoid caps
    res = sizing_service.calculate(uuid.uuid4(), p_market=0.3, q_raw=0.8)
    assert abs(res.q_adj - 0.55) < 1e-4
    assert abs(res.p_eff - 0.35) < 1e-4
    assert abs(res.edge_net - 0.20) < 1e-4
    assert abs(res.f_full - 0.307692) < 1e-4
    assert abs(res.f_half - 0.153846) < 1e-4
    assert abs(res.f_final - 0.153846) < 1e-4

def test_sizing_alpha_discount(sizing_service):
    """Sizing: alpha 折扣因子有效缩减主观概率优势"""
    sizing_service._config["max_position_size_usd"] = 10000.0
    res1 = sizing_service.calculate(uuid.uuid4(), p_market=0.3, q_raw=0.8)
    
    sizing_service._config["alpha"] = 1.0
    res2 = sizing_service.calculate(uuid.uuid4(), p_market=0.3, q_raw=0.8)
    assert res2.q_adj == 0.8
    assert res2.f_final > res1.f_final

def test_sizing_taker_fee_reject(sizing_service):
    """Sizing: taker 成本导致可交易机会变成不可交易"""
    res1 = sizing_service.calculate(uuid.uuid4(), p_market=0.3, q_raw=0.35)
    assert res1.f_final == 0.0
    assert "Net edge is zero or negative." in res1.sizing_reason_codes
    
    sizing_service._config["taker_fee_per_share"] = 0.0
    sizing_service._config["expected_slippage_per_share"] = 0.0
    sizing_service._config["exit_cost_reserve"] = 0.0
    sizing_service._config["uncertainty_haircut"] = 0.0
    res2 = sizing_service.calculate(uuid.uuid4(), p_market=0.3, q_raw=0.35)
    assert res2.f_final > 0

@pytest.mark.asyncio
async def test_risk_spread_limit(risk_service):
    """Risk: spread 超限导致触发拒绝断言"""
    payload = {
        "market_name": "polymarket",
        "spread_pct": 0.15,
        "hours_to_expiry": 48.0
    }
    res = await risk_service.check(uuid.uuid4(), payload)
    assert not res.allow
    assert any("Spread" in code for code in res.reason_codes)

@pytest.mark.asyncio
async def test_risk_near_expiry_limit(risk_service):
    """Risk: near-expiry 临期天数/小时内限制生效"""
    payload = {
        "market_name": "polymarket",
        "hours_to_expiry": 12.0,
    }
    res = await risk_service.check(uuid.uuid4(), payload)
    assert not res.allow
    assert any("Expiry" in code for code in res.reason_codes)
