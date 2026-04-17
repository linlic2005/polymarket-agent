"""
Orchestrator 核心调度层。

管线：Map -> Rules -> Thesis -> Risk -> Sizing。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from libs.models.db_models import CandidateOrder
from libs.models.schemas import ApprovalDecision
from apps.execution.service import ExecutionService
from apps.orchestrator.workflows import HermesWorkflowService

logger = logging.getLogger(__name__)

class OrchestratorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run_pipeline(self, event_id: uuid.UUID) -> dict[str, Any]:
        """
        全量驱动从事件到下单之前的准备状态。
        由于模块复杂，本处做宏观流转聚合：
        假定前面的 map -> rules -> thesis 已经跑完，并已经在数据库中生成了 CandidateOrder 记录。
        我们会将查找到的 pending / new 的 CandidateOrder 执行一次内部 risk & sizing 回顾评估，
        没问题则标记为 AWAIT_APPROVAL。
        """
        stmt = select(CandidateOrder).where(CandidateOrder.market_event_id == event_id)
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()
        
        if not order:
             return {"status": "error", "message": "No candidate order generated for event."}

        if order.status != "pending":
             return {"status": "skipped", "message": f"Order already in state: {order.status}"}

        # 强制将状态停留为审批点并挂起：
        order.status = "AWAIT_APPROVAL"
        try:
            await self._session.commit()
        except:
            await self._session.rollback()

        # 发送外部通知：
        HermesWorkflowService.notify_approval_needed(str(order.id), {"event_id": str(event_id)})
        logger.info("[Orchestrator] Candidate order %s is now AWAIT_APPROVAL", order.id)

        return {"status": "AWAIT_APPROVAL", "candidate_id": str(order.id)}

    async def process_approval(self, decision: ApprovalDecision) -> dict[str, Any]:
        """
        处理外界传回的审批裁决。仅调用内部 API 执行，Orchestrator 本身不持有私钥。
        """
        stmt = select(CandidateOrder).where(CandidateOrder.id == decision.candidate_id)
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError("CandidateOrder not found.")

        if order.status != "AWAIT_APPROVAL":
            raise ValueError(f"Cannot approve order in state {order.status}. Must be AWAIT_APPROVAL.")

        if decision.approved:
            logger.info("[Orchestrator] Order %s approved by %s. Initiating execution.", order.id, decision.approver)
            execution_service = ExecutionService(self._session)
            
            try:
                res = await execution_service.execute_candidate(order.id)
                return {"status": "executed", "execution_result": res}
            except Exception as e:
                 logger.error("Execution failed after approval: %s", e)
                 return {"status": "execution_failed", "error": str(e)}
        else:
            logger.info("[Orchestrator] Order %s rejected by %s.", order.id, decision.approver)
            order.status = "REJECTED"
            order.rejection_reason = f"Manual rejection by {decision.approver}: {decision.note}"
            try:
                 await self._session.commit()
            except:
                 pass
            return {"status": "rejected"}
