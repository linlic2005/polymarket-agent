"""
Mapper 业务服务。

职责：
1. 接收 MarketEvent，通过关键词 / 语义匹配找到对应的 Polymarket 条件市场
2. 记录映射关系
3. 应用市场白名单过滤
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import IngestEvent, CandidateMarket
from libs.models.schemas import CandidateMarketRead
from libs.utils.yaml_loader import load_markets_whitelist
from apps.mapper.polymarket_market_client import PolymarketMarketClient

logger = logging.getLogger(__name__)


def compute_mapping_score(event_headline: str, event_tags: list[str], pm_title: str) -> float:
    """
    启发式评分函数，计算外部事件和 Polymarket 市场的匹配度。
    简单的文本重合度计算思路，实际应用可以替换为 LLM 或 Embedding 相似度。
    """
    score = 0.0
    
    # 标题交集
    event_words = set(event_headline.lower().split())
    pm_words = set(pm_title.lower().split())
    
    if event_words and pm_words:
        intersection = event_words.intersection(pm_words)
        score += float(len(intersection)) / len(event_words) * 0.5
        
    # 标签匹配
    tags_lower = {t.lower() for t in event_tags}
    if tags_lower and pm_words:
        tag_hits = tags_lower.intersection(pm_words)
        score += float(len(tag_hits)) / max(len(tags_lower), 1) * 0.5
        
    return min(score + 0.1, 1.0)  # 微小底分，上限1.0


class MapperService:
    """事件→市场映射服务。"""

    def __init__(self, session: AsyncSession, market_client: PolymarketMarketClient | None = None) -> None:
        self._session = session
        self._whitelist = load_markets_whitelist()
        self._market_client = market_client or PolymarketMarketClient()

    async def map_event_to_markets(self, event_id: uuid.UUID) -> dict[str, Any]:
        """
        将事件映射到 Polymarket 条件市场。

        流程：
        1. 加载 IngestEvent 事件详情
        2. 结合 tags 和 headline 调用 PM client 进行搜索
        3. 对搜出的市场，进行 mapping_score 计算
        4. 应用白名单与可交易状态(active)过滤
        5. 对高分市场存入 candidate_markets 并返回映射结果
        """
        event = await self._session.get(IngestEvent, event_id)
        if event is None:
            raise ValueError(f"事件不存在: {event_id}")

        query_terms = event.entity_tags + event.symbol_tags
        query_str = " ".join(query_terms) if query_terms else event.headline
        
        logger.info("[MapperService] Searching Polymarket for: %s", query_str)
        pm_events = await self._market_client.search_events(query_str)
        
        matched_candidates = []
        
        for pm_evt in pm_events:
            for market in pm_evt.get("markets", []):
                # 基本过滤
                if not market.get("active", False) or market.get("closed", True):
                    continue
                    
                cond_id = market.get("conditionId")
                if not self._is_whitelisted(None, cond_id):
                    continue
                    
                score = compute_mapping_score(event.headline, event.entity_tags, market.get("question", ""))
                
                # 若得分过低直接丢弃
                if score < 0.2:
                    continue
                    
                # 提取 tokens
                tokens = market.get("tokens", [])
                token_yes = next((t["token_id"] for t in tokens if t.get("outcome", "").upper() == "YES"), "unknown_yes")
                token_no = next((t["token_id"] for t in tokens if t.get("outcome", "").upper() == "NO"), "unknown_no")
                
                # 存入库
                candidate = CandidateMarket(
                    event_id=event.event_id,
                    polymarket_event_slug=pm_evt.get("slug", ""),
                    market_slug=market.get("slug", ""),
                    token_yes=token_yes,
                    token_no=token_no,
                    mapping_score=score,
                    fees_enabled=True,
                )
                self._session.add(candidate)
                await self._session.flush()
                await self._session.refresh(candidate)
                
                matched_candidates.append(CandidateMarketRead.model_validate(candidate).model_dump(mode="json"))

        return {
            "event_id": str(event_id),
            "title": event.headline,
            "matched_markets": matched_candidates,
            "status": "success" if matched_candidates else "no_match",
        }

    async def list_mappings(
        self, *, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """查询已完成的事件-市场映射列表。"""
        stmt = select(CandidateMarket).order_by(CandidateMarket.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        candidates = result.scalars().all()
        
        return {
            "mappings": [CandidateMarketRead.model_validate(c).model_dump(mode="json") for c in candidates], 
            "total": len(candidates), 
            "limit": limit, 
            "offset": offset
        }

    def _is_whitelisted(self, category: str | None, condition_id: str | None) -> bool:
        """检查市场是否在白名单中。"""
        if not self._whitelist.get("enabled", True):
            return True

        blocked = self._whitelist.get("blocked_condition_ids", [])
        if condition_id and condition_id in blocked:
            return False

        allowed_cats = self._whitelist.get("allowed_categories", [])
        if category and category in allowed_cats:
            return True

        allowed_ids = self._whitelist.get("allowed_condition_ids", [])
        if allowed_ids and condition_id and condition_id in allowed_ids:
            return True

        # 如果都没有命中且有限制，则默认不过，为了演示简单起见，这里假设通过（因为之前的逻辑在有配置项限制时默认False）
        # 保持与旧逻辑一致：
        if allowed_cats or allowed_ids:
            return False
            
        return True
