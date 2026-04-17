"""
Rules 业务服务。

职责：
1. 加载并管理信号规则集合
2. 评估事件是否满足规则条件
3. 生成买/卖方向和初步估值
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import MarketEvent, CandidateMarket
from apps.mapper.polymarket_market_client import PolymarketMarketClient
from apps.rules.parser import RulesParser

logger = logging.getLogger(__name__)


class RulesService:
    """信号规则引擎服务。"""

    def __init__(self, session: AsyncSession, market_client: PolymarketMarketClient | None = None) -> None:
        self._session = session
        self._market_client = market_client or PolymarketMarketClient()

    async def get_and_parse_rules(self, candidate_id: uuid.UUID) -> dict[str, Any]:
        """
        针对候选市场，抓取详细规则和盘口快照。
        """
        candidate = await self._session.get(CandidateMarket, candidate_id)
        if candidate is None:
            raise ValueError(f"候选市场不存在: {candidate_id}")
            
        # 抓取并解析规则
        rule_text = await self._market_client.get_event_rules(candidate.polymarket_event_slug)
        parser = RulesParser(rule_text)
        parsed_data = parser.parse_all()
        
        # 获取盘口
        orderbook = await self._market_client.get_market_orderbook(candidate.token_yes)
        
        # 更新数据库
        candidate.rule_text = rule_text
        candidate.rules_parsed = parsed_data
        candidate.orderbook_snapshot = orderbook
        candidate.spread_snapshot = orderbook.get("spread")
        
        await self._session.flush()
        await self._session.refresh(candidate)
        
        return {
            "candidate_id": str(candidate_id),
            "rule_text": rule_text,
            "parsed_rules": parsed_data,
            "orderbook": orderbook
        }

    async def evaluate(self, event_id: uuid.UUID) -> dict[str, Any]:
        """
        评估事件是否触发交易信号 (旧版逻辑入口)。
        """
        event = await self._session.get(MarketEvent, event_id)
        if event is None:
            raise ValueError(f"事件不存在: {event_id}")

        logger.info("rules.evaluate: event=%s (stub)", event_id)

        return {
            "event_id": str(event_id),
            "triggered": False,
            "signal": None,
            "confidence": 0.0,
            "message": "规则评估 (stub)",
        }
