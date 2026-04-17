"""
Reporting 报表统计服务。
由于底层使用的是异步 SQLAlchemy Session，支持从各核心表按时间段拉取并聚合流水账本。
"""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from libs.models.db_models import IngestEvent, CandidateOrder, Position
from libs.models.schemas import DailyReport

logger = logging.getLogger(__name__)

class ReportingService:
    def __init__(self, session: AsyncSession) -> None:
         self._session = session
         
    async def generate_daily_report(self) -> DailyReport:
         """生成以当前结算周期（假定 UTC 的今日）为标尺的日结表。"""
         today_str = datetime.now(UTC).strftime("%Y-%m-%d")
         
         # 1. 接收事件数
         stmt_events = select(func.count(IngestEvent.event_id))
         res1 = await self._session.execute(stmt_events)
         events_received = res1.scalar() or 0
         
         # 2. 候选单数
         stmt_candidates = select(func.count(CandidateOrder.id))
         res2 = await self._session.execute(stmt_candidates)
         candidates_generated = res2.scalar() or 0
         
         # 3. 风控拒绝数
         stmt_rejected = select(func.count(CandidateOrder.id)).where(CandidateOrder.status == 'REJECTED')
         res3 = await self._session.execute(stmt_rejected)
         risk_rejected = res3.scalar() or 0
         
         # 4. 审批数 -> AWAIT_APPROVAL 以及被决断过流转的状态
         stmt_approval = select(func.count(CandidateOrder.id)).where(CandidateOrder.status.not_in(['pending', 'NEW_CANDIDATE', 'READY_TO_PLACE']))
         res4 = await self._session.execute(stmt_approval)
         approval_granted = res4.scalar() or 0
         
         # 5. 下单数 -> PLACED 及以上
         stmt_placed = select(func.count(CandidateOrder.id)).where(CandidateOrder.status.in_(['PLACED', 'PARTIALLY_FILLED', 'FILLED']))
         res5 = await self._session.execute(stmt_placed)
         orders_placed = res5.scalar() or 0
         
         # 6. 成交数 
         stmt_filled = select(func.count(CandidateOrder.id)).where(CandidateOrder.status == 'FILLED')
         res6 = await self._session.execute(stmt_filled)
         orders_filled = res6.scalar() or 0
         
         # 7. 当前持仓与 PNL
         stmt_pos = select(Position)
         res7 = await self._session.execute(stmt_pos)
         positions = res7.scalars().all()
         
         current_positions_count = len([p for p in positions if p.size > 0])
         realized_pnl = sum(p.realised_pnl for p in positions)
         unrealized_pnl = sum(p.unrealised_pnl for p in positions if p.size > 0)
         
         report = DailyReport(
              date=today_str,
              events_received_count=events_received,
              candidates_generated_count=candidates_generated,
              risk_rejected_count=risk_rejected,
              approval_granted_count=approval_granted,
              orders_placed_count=orders_placed,
              orders_filled_count=orders_filled,
              current_positions_count=current_positions_count,
              realized_pnl_usd=realized_pnl,
              unrealized_pnl_usd=unrealized_pnl
         )
         return report
