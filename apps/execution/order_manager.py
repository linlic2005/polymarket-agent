r"""
Execution Order Manager.
控制订单状态机的单向流转。

状态路径：
NEW_CANDIDATE -> READY_TO_PLACE -> PLACED -> PARTIALLY_FILLED -> FILLED
             \                             \-> EXIT_PENDING -> EXITED / CANCELLED
              \-> REJECTED
"""

import logging
from typing import Optional

from libs.adapters.polymarket_base import PolymarketBaseAdapter
from libs.models.db_models import CandidateOrder

logger = logging.getLogger(__name__)


class OrderManager:
    """订单生命周期状态机管理器。"""

    def __init__(self, adapter: PolymarketBaseAdapter) -> None:
        self.adapter = adapter

    async def initialize_order(self, order: CandidateOrder) -> None:
        """从 NEW_CANDIDATE -> READY_TO_PLACE"""
        if order.status not in ("pending", "NEW_CANDIDATE"):
            logger.warning("Order %s is not pending/new.", order.id)
            return

        order.status = "READY_TO_PLACE"
        logger.info("[OrderManager] Order %s state -> READY_TO_PLACE", order.id)

    async def place_order(self, order: CandidateOrder) -> dict:
        """执行下单动作，从 READY_TO_PLACE -> PLACED 或 FILLED"""
        if order.status != "READY_TO_PLACE":
            raise ValueError(f"Cannot place order from state {order.status}")

        logger.info("[OrderManager] Executing place_limit_order for %s", order.id)
        token_id = f"{order.polymarket_condition_id}_{order.outcome}"
        
        try:
            res = await self.adapter.place_limit_order(
                token_id=token_id,
                price=order.target_price,
                size=order.size,
                side=order.side,
            )
            logger.info("[OrderManager] Adapter returned: %s", res)
            
            next_status = "PLACED"
            if res.get("status") == "FILLED":
                next_status = "FILLED"
            elif res.get("status") == "PARTIALLY_FILLED":
                next_status = "PARTIALLY_FILLED"
                
            order.status = next_status
            return res
        except Exception as e:
            logger.error("[OrderManager] Failed to place order %s: %s", order.id, e)
            order.status = "REJECTED"
            order.rejection_reason = str(e)
            raise e

    async def cancel_order(self, order: CandidateOrder, execution_id: str) -> bool:
        """处理订单取消，从 PLACED -> CANCELLED"""
        if order.status not in ["PLACED", "PARTIALLY_FILLED", "READY_TO_PLACE"]:
            raise ValueError(f"Cannot cancel order from current state {order.status}")
            
        success = await self.adapter.cancel_order(execution_id)
        if success:
            order.status = "CANCELLED"
            logger.info("[OrderManager] Order %s state -> CANCELLED.", order.id)
        return success

    async def exit_position(self, order: CandidateOrder) -> None:
        """平仓态变迁 FILLED -> EXIT_PENDING -> EXITED"""
        if order.status != "FILLED":
            raise ValueError(f"Cannot exit from state {order.status}")
        order.status = "EXIT_PENDING"
        # 实际这里会触发新的卖出/买入相对订单
        order.status = "EXITED"
        logger.info("[OrderManager] Position for order %s state -> EXITED.", order.id)
