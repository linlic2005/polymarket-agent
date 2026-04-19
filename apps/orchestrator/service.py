"""
Orchestrator 核心调度层。

管线：Map -> Rules -> Thesis -> Risk -> Sizing -> CandidateOrder -> AWAIT_APPROVAL。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from libs.models.db_models import CandidateOrder, CandidateMarket, IngestEvent
from libs.models.schemas import ApprovalDecision
from apps.execution.service import ExecutionService
from apps.mapper.service import MapperService
from apps.rules.service import RulesService
from apps.thesis.service import ThesisService
from apps.risk_engine.service import RiskEngineService
from apps.sizing.service import SizingService
from apps.orchestrator.workflows import HermesWorkflowService

logger = logging.getLogger(__name__)


class OrchestratorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run_pipeline(self, event_id: uuid.UUID) -> dict[str, Any]:
        """
        全量驱动从事件到下单之前的准备状态。

        流程：
        1. 验证事件存在
        2. Mapper: 事件 → Polymarket 市场（创建 CandidateMarket）
        3. Rules: 拉取并解析市场规则（更新 CandidateMarket）
        4. Thesis: 生成交易论点（创建 ThesisHistory）
        5. Risk: 风控检查（创建 RiskHistory）
        6. Sizing: 仓位计算（创建 SizingHistory）
        7. 若 risk allow=True 且 sizing f_final > 0 → 创建 CandidateOrder → AWAIT_APPROVAL
        8. 若 risk allow=False 或 sizing ≤ 0 → 记录拒绝原因，不下发
        """
        # 1. 验证事件存在
        event = await self._session.get(IngestEvent, event_id)
        if event is None:
            return {"status": "error", "message": f"Event not found: {event_id}"}

        # 2. Mapper: 事件 → 市场映射
        mapper = MapperService(self._session)
        map_result = await mapper.map_event_to_markets(event_id)
        matched_markets = map_result.get("matched_markets", [])
        if not matched_markets:
            return {"status": "no_match", "message": "No candidate markets matched for this event."}

        # 取第一个最佳候选市场
        best_market = matched_markets[0]
        candidate_id = best_market["candidate_id"]

        # 验证 CandidateMarket 存在
        candidate_market = await self._session.get(CandidateMarket, uuid.UUID(candidate_id))
        if candidate_market is None:
            return {"status": "error", "message": f"CandidateMarket not found: {candidate_id}"}

        # 3. Rules: 拉取并解析规则
        rules_svc = RulesService(self._session)
        rules_result = await rules_svc.get_and_parse_rules(uuid.UUID(candidate_id))
        logger.info("[Orchestrator] Rules parsed for candidate %s", candidate_id)

        # 4. Thesis: 生成交易论点
        thesis_svc = ThesisService(self._session)
        thesis_result = await thesis_svc.generate(uuid.UUID(candidate_id))
        logger.info("[Orchestrator] Thesis generated: direction=%s confidence=%.2f",
                    thesis_result.direction, thesis_result.confidence)

        # 5. Risk: 风控检查
        risk_payload = {
            "market_name": candidate_market.market_slug or "unknown",
            "current_market_risk_usd": 0.0,
            "current_theme_risk_usd": 0.0,
            "daily_new_risk_usd": 0.0,
            "daily_loss_usd": 0.0,
            "orderbook_depth_usd": 500.0,
            "spread_pct": candidate_market.spread_snapshot or 0.05,
            "estimated_slippage_pct": 0.01,
            "expected_hold_minutes": thesis_result.max_hold_minutes,
            "hours_to_expiry": candidate_market.time_to_resolution or 48.0,
            "order_risk_usd": 100.0,
        }
        risk_svc = RiskEngineService(self._session)
        risk_decision = await risk_svc.check(uuid.UUID(candidate_id), risk_payload)
        logger.info("[Orchestrator] Risk check: allow=%s reasons=%s",
                    risk_decision.allow, risk_decision.reason_codes)

        if not risk_decision.allow:
            # 风控拒绝，创建拒绝状态的 CandidateOrder
            order = CandidateOrder(
                market_event_id=event_id,
                polymarket_condition_id=candidate_market.market_slug,
                side="BUY",
                outcome=thesis_result.direction,
                target_price=0.5,
                size=0.0,
                status="REJECTED",
                dry_run=True,
                thesis_summary=thesis_result.reasoning_summary,
                risk_score=50.0 if risk_decision.reason_codes else None,
                rejection_reason="; ".join(risk_decision.reason_codes) if risk_decision.reason_codes else "Risk rejected",
            )
            self._session.add(order)
            await self._session.flush()
            await self._session.refresh(order)
            logger.info("[Orchestrator] Order %s REJECTED by risk engine", order.id)
            return {
                "status": "rejected",
                "candidate_id": str(order.id),
                "reasons": risk_decision.reason_codes
            }

        # 6. Sizing: 仓位计算
        sizing_svc = SizingService(self._session)
        sizing_decision = sizing_svc.calculate(
            candidate_id=uuid.UUID(candidate_id),
            p_market=thesis_result.p_market,
            q_raw=thesis_result.q_raw,
        )
        logger.info("[Orchestrator] Sizing calculated: f_final=%.4f edge_net=%.3f",
                    sizing_decision.f_final, sizing_decision.edge_net)

        if sizing_decision.f_final <= 0:
            order = CandidateOrder(
                market_event_id=event_id,
                polymarket_condition_id=candidate_market.market_slug,
                side="BUY",
                outcome=thesis_result.direction,
                target_price=0.5,
                size=0.0,
                status="REJECTED",
                dry_run=True,
                thesis_summary=thesis_result.reasoning_summary,
                risk_score=0.0,
                rejection_reason=f"Sizing non-positive: edge_net={sizing_decision.edge_net:.4f}",
            )
            self._session.add(order)
            await self._session.flush()
            await self._session.refresh(order)
            logger.info("[Orchestrator] Order %s REJECTED by sizing (edge_net=%.4f)",
                        order.id, sizing_decision.edge_net)
            return {
                "status": "rejected",
                "candidate_id": str(order.id),
                "reason": f"Sizing zero or negative (edge_net={sizing_decision.edge_net:.4f})"
            }

        # 7. 创建 CandidateOrder 并进入 AWAIT_APPROVAL
        # 计算 target_price: 如果做多 YES，用市价 + 小折扣
        target_price = 0.5  # 默认中间价
        spread = candidate_market.spread_snapshot or 0.01
        if thesis_result.direction == "YES":
            target_price = max(0.01, 0.5 - spread * 0.5)
        else:
            target_price = min(0.99, 0.5 + spread * 0.5)

        order = CandidateOrder(
            market_event_id=event_id,
            polymarket_condition_id=candidate_market.market_slug,
            side="BUY",
            outcome=thesis_result.direction,
            target_price=target_price,
            size=sizing_decision.f_final,
            status="AWAIT_APPROVAL",
            dry_run=True,
            thesis_summary=thesis_result.reasoning_summary,
            risk_score=0.0,
        )
        self._session.add(order)
        await self._session.flush()
        await self._session.refresh(order)

        try:
            await self._session.commit()
        except:
            await self._session.rollback()
            raise

        # 8. 发送 Hermes 审批通知
        HermesWorkflowService.notify_approval_needed(str(order.id), {
            "event_id": str(event_id),
            "candidate_id": str(order.id),
            "direction": thesis_result.direction,
            "edge_net": sizing_decision.edge_net,
            "size": sizing_decision.f_final,
        })
        logger.info("[Orchestrator] Candidate order %s is now AWAIT_APPROVAL", order.id)

        return {
            "status": "AWAIT_APPROVAL",
            "candidate_id": str(order.id),
            "direction": thesis_result.direction,
            "edge_net": sizing_decision.edge_net,
            "size": sizing_decision.f_final,
            "p_market": thesis_result.p_market,
            "q_raw": thesis_result.q_raw,
        }

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
