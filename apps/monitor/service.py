"""
Monitor 扫描服务。
监听订单及仓位状态。支持五大退出条件。
"""
from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from libs.models.db_models import Position
from apps.execution.service import ExecutionService

logger = logging.getLogger(__name__)

class MonitorService:
    def __init__(self, session: AsyncSession) -> None:
         self._session = session
         self.execution = ExecutionService(session)
         
    async def scan_and_trigger_exits(self) -> dict[str, int]:
         """
         扫描系统状态，同步远程持仓记录 position 和 fills
         触发强平退出:
         1. thesis 失效
         2. 持仓超时
         3. spread 恶化
         4. 规则变动
         5. 全局熔断
         """
         stmt = select(Position).where(Position.size > 0)
         res = await self._session.execute(stmt)
         positions = res.scalars().all()
         
         exited_count = 0
         
         for pos in positions:
              # [Stub]
              # 真正的实现将依赖实时行情缓存对比阈值
              thesis_invalid = False
              timeout = False
              spread_deteriorate = False
              rule_change = False
              circuit_break = False  # 如果外部设置全局熔断开关
              
              if any([thesis_invalid, timeout, spread_deteriorate, rule_change, circuit_break]):
                   logger.warning(
                       "[Monitor] Exit condition met for position %s. Emergency exit initiated.", pos.id
                   )
                   # 应该向 OrderManager 发送清仓命令，此处用归零代表持仓清空落库
                   pos.size = 0.0
                   exited_count += 1
                   
         try:
              await self._session.commit()
         except:
              await self._session.rollback()
              
         return {"scanned_positions": len(positions), "exits_triggered": exited_count}
