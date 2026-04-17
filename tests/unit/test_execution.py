"""
Execution 模块的测试用例。
- 保证 paper 模拟器的下单、填充动作完备
- 测试 OrderManager 的单向状态机能否正确拦截异常
- 确保 ExecutionService 可以拒绝非法前置状态
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from libs.models.db_models import CandidateOrder
from libs.adapters.polymarket_paper import PolymarketPaperAdapter
from libs.adapters.polymarket_live import PolymarketLiveAdapter
from apps.execution.order_manager import OrderManager

class MockSession:
    def __init__(self, stub_order=None):
        self.stub_order = stub_order
        self.added = []
    
    async def execute(self, stmt):
        class MockResult:
            def scalar_one_or_none(self_):
                return self.stub_order
        return MockResult()

    def add(self, entity):
        self.added.append(entity)
        
    async def commit(self):
        pass
        
    async def rollback(self):
        pass

@pytest.fixture
def paper_adapter():
    return PolymarketPaperAdapter()

@pytest.fixture
def test_order():
    o = CandidateOrder()
    o.id = uuid.uuid4()
    o.status = "pending"
    o.polymarket_condition_id = "cond_123"
    o.outcome = "YES"
    o.side = "BUY"
    o.target_price = 0.5
    o.size = 100.0
    o.risk_score = 10.0
    return o

@pytest.mark.asyncio
async def test_paper_adapter_dry_run(paper_adapter):
    res = await paper_adapter.place_limit_order("cond_YES", 0.5, 100, "BUY")
    assert res["status"] == "FILLED"
    assert res["filled_size"] == 100
    
    open_orders = await paper_adapter.get_open_orders()
    assert len(open_orders) == 0
    
    positions = await paper_adapter.get_positions()
    assert len(positions) == 1
    assert positions[0]["amount"] == 100

@pytest.mark.asyncio
async def test_order_manager_transitions(paper_adapter, test_order):
    manager = OrderManager(paper_adapter)
    
    await manager.initialize_order(test_order)
    assert test_order.status == "READY_TO_PLACE"
    
    await manager.place_order(test_order)
    assert test_order.status == "FILLED"
    
    await manager.exit_position(test_order)
    assert test_order.status == "EXITED"

@pytest.mark.asyncio
async def test_service_pre_checks_rejects_zero_size(test_order):
    from apps.execution.service import ExecutionService
    test_order.size = 0.0
    session = MockSession(stub_order=test_order)
    
    with patch("apps.execution.service.get_settings") as mock_settings:
        mock_settings.return_value.dry_run = True
        service = ExecutionService(session)
        
    with pytest.raises(ValueError, match="Invalid sizing"):
        await service.execute_candidate(test_order.id)
    assert session.added[0].status == "REJECTED"

@pytest.mark.asyncio
async def test_service_pre_checks_rejects_risk(test_order):
    from apps.execution.service import ExecutionService
    test_order.risk_score = 80.0
    session = MockSession(stub_order=test_order)
    
    with patch("apps.execution.service.get_settings") as mock_settings:
        mock_settings.return_value.dry_run = True
        service = ExecutionService(session)
        
    with pytest.raises(ValueError, match="Blocked by risk engine"):
        await service.execute_candidate(test_order.id)
