"""
Execution 业务服务。

职责：
1. 接收外部 candidate_id，重组上下文查验风控
2. 分配对应 Adapter（dry_run / paper / live）
3. 使用 OrderManager 推进状态机
4. 将所有执行行为记入 audit_logs (基于 ExecutionRecord)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from libs.models.db_models import CandidateOrder, ExecutionRecord
from libs.models.settings import get_settings
from libs.adapters.polymarket_paper import PolymarketPaperAdapter
from libs.adapters.polymarket_live import PolymarketLiveAdapter
from apps.execution.order_manager import OrderManager

logger = logging.getLogger(__name__)


class ExecutionService:
    """订单执行调度服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

        # 根据 dry_run 开关分配适配器模式
        if self._settings.dry_run:
            self.adapter = PolymarketPaperAdapter()
        else:
            self.adapter = PolymarketLiveAdapter()

        self.order_manager = OrderManager(self.adapter)

    async def _audit_log(
        self, order_id: uuid.UUID, action: str, details: str, ext_id: str | None = None
    ) -> None:
        """记录执行流水至数据库 audit logs."""
        record = ExecutionRecord(
            candidate_order_id=order_id,
            exchange_order_id=ext_id,
            status=action,
            dry_run=self._settings.dry_run,
            error_message=details
        )
        self._session.add(record)
        try:
            await self._session.commit()
        except:
            await self._session.rollback()

    async def execute_candidate(self, candidate_id: uuid.UUID) -> dict[str, Any]:
        """从外部端点被叫起，全流程执行候选单。"""
        stmt = select(CandidateOrder).where(CandidateOrder.id == candidate_id)
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError(f"CandidateOrder {candidate_id} not found.")

        # ========================================
        # 强制性前置拦截校验 (Pre-Execution Checks)
        # ========================================
        # 1. 确认是否经过 Sizing 计算
        if order.size <= 0:
            await self._audit_log(order.id, "REJECTED", "Sizing validation failed (size <= 0).")
            raise ValueError("Invalid sizing.")

        # 2. Risk 复查
        if order.risk_score and order.risk_score > 50:
            await self._audit_log(order.id, "REJECTED", "Risk score too high.")
            raise ValueError("Blocked by risk engine.")

        # 3. Geoblock API 预留防线
        geoblocked = False  # Placeholder
        if geoblocked:
            await self._audit_log(order.id, "REJECTED", "Geoblocked IP range.")
            raise ValueError("Geoblocked location.")

        # 4. 断言不是已经被拒状态
        if order.status == "REJECTED":
            raise ValueError("Order is already rejected.")

        # ========================================
        # 状态机初始化与下单动作
        # ========================================
        order.status = "NEW_CANDIDATE"
        await self.order_manager.initialize_order(order)
        await self._session.commit()
        await self._audit_log(order.id, "READY_TO_PLACE", "Initialized successfully.")

        try:
            place_res = await self.order_manager.place_order(order)
            await self._session.commit()
            await self._audit_log(
                order.id, 
                order.status, 
                "Order command sent.", 
                ext_id=place_res.get("id")
            )
            return place_res
        except Exception as e:
            await self._session.commit()
            await self._audit_log(order.id, "REJECTED", f"Exception placing order: {str(e)}")
            raise e

    async def cancel_order_request(self, order_id: uuid.UUID, execution_id: str) -> bool:
        """撤单请求逻辑。"""
        stmt = select(CandidateOrder).where(CandidateOrder.id == order_id)
        result = await self._session.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError("Order not found in DB.")

        success = await self.order_manager.cancel_order(order, execution_id)
        await self._session.commit()
        if success:
            await self._audit_log(order.id, "CANCELLED", "Order successfully cancelled.", ext_id=execution_id)
        return success

    async def fetch_open_orders(self) -> list[dict[str, Any]]:
        return await self.adapter.get_open_orders()

    async def fetch_positions(self) -> list[dict[str, Any]]:
        return await self.adapter.get_positions()
