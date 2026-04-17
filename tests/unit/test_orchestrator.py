"""
Orchestrator 断言测试。
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from libs.models.db_models import CandidateOrder
from libs.models.schemas import ApprovalDecision
from apps.orchestrator.service import OrchestratorService

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
def mock_order():
    o = CandidateOrder()
    o.id = uuid.uuid4()
    o.market_event_id = uuid.uuid4()
    o.status = "pending"
    return o

@pytest.mark.asyncio
async def test_orchestrator_pipeline_stops_at_await_approval(mock_order):
    session = MockSession(stub_order=mock_order)
    service = OrchestratorService(session)
    
    with patch("apps.orchestrator.workflows.HermesWorkflowService.notify_approval_needed") as mock_notify:
        res = await service.run_pipeline(mock_order.market_event_id)
        
        assert res["status"] == "AWAIT_APPROVAL"
        assert mock_order.status == "AWAIT_APPROVAL"
        mock_notify.assert_called_once()

@pytest.mark.asyncio
async def test_orchestrator_reject_approval(mock_order):
    mock_order.status = "AWAIT_APPROVAL"
    session = MockSession(stub_order=mock_order)
    service = OrchestratorService(session)
    
    decision = ApprovalDecision(
        candidate_id=mock_order.id,
        approved=False,
        approver="test_user",
        note="Too risky"
    )
    
    res = await service.process_approval(decision)
    assert res["status"] == "rejected"
    assert mock_order.status == "REJECTED"
    assert "Too risky" in mock_order.rejection_reason

@pytest.mark.asyncio
async def test_orchestrator_accept_approval_calls_execution(mock_order):
    mock_order.status = "AWAIT_APPROVAL"
    session = MockSession(stub_order=mock_order)
    service = OrchestratorService(session)
    
    decision = ApprovalDecision(
        candidate_id=mock_order.id,
        approved=True,
        approver="test_user"
    )
    
    with patch("apps.orchestrator.service.ExecutionService") as MockExecService:
        mock_exec_instance = MockExecService.return_value
        mock_exec_instance.execute_candidate = AsyncMock(return_value={"status": "PLACED"})
        
        res = await service.process_approval(decision)
        
        assert res["status"] == "executed"
        mock_exec_instance.execute_candidate.assert_called_once_with(mock_order.id)
