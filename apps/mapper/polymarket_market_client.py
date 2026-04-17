"""
Polymarket Market Data API Client.

封装了针对 Polymarket 市场信息 (Gamma API) 的查询逻辑。
用于 mapper 模块搜索市场以及 rules/execution 模块查询市场最新快照。
此处为 mock/抽象 实现，便于后续替换为官方 SDK 实际调用。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PolymarketMarketClient:
    """Polymarket 市场数据查询终端。"""

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com") -> None:
        self.base_url = base_url
        self._http: httpx.AsyncClient | None = None

    async def _get_http(self) -> httpx.AsyncClient:
        """懒加载 HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=15.0,
            )
        return self._http

    async def search_events(self, query: str) -> list[dict[str, Any]]:
        """
        根据指定条件搜索聚合事件(events)。
        
        Args:
            query: 搜索关键词 (实际应用中可能复杂很多)
            
        Returns:
            市场事件字典的列表
        """
        # TODO: 接入对应 API, 例如: GET /events?query={query}
        # 目前返回 MOCK 数据，用于演示结构
        if not query:
            return []
            
        logger.info("[PolymarketMarketClient] search_events(query=%r) (stub)", query)

        return [
            {
                "id": "poly_evt_001",
                "slug": "will-trump-do-something",
                "title": f"Polymarket Event matching {query}",
                "markets": [
                    {
                        "conditionId": "0x123",
                        "slug": "will-trump-do-something-yes",
                        "question": "Will Trump do something?",
                        "groupItemTitle": "Yes",
                        "tokens": [
                            {"outcome": "Yes", "token_id": "token_yes_123"},
                            {"outcome": "No", "token_id": "token_no_123"}
                        ],
                        "active": True,
                        "closed": False,
                    }
                ]
            }
        ]

    async def get_event_rules(self, event_slug: str) -> str:
        """
        根据 event slug 获取详细的 rule_text，通常包含判定源、过期细节等。
        
        Args:
            event_slug: 事件 Slug
            
        Returns:
            解析出的规则文本字符串
        """
        # TODO: GET /events/{event_slug} 或抓取前端页面提取规则
        logger.info("[PolymarketMarketClient] get_event_rules(event_slug=%r) (stub)", event_slug)
        return "Rules details: If resolution source X reports YES before Date Y, the market resolves to YES. Otherwise NO."

    async def get_market_orderbook(self, token_id: str) -> dict[str, Any]:
        """
        获取指定 token (Outcome) 的 Orderbook。
        
        Args:
            token_id: Outcome Token ID (如 YES 的 tokenId)
        """
        # TODO: GET /orderbook/{token_id}
        logger.info("[PolymarketMarketClient] get_market_orderbook(token_id=%r) (stub)", token_id)
        return {
            "bids": [{"price": 0.49, "size": 1000}],
            "asks": [{"price": 0.51, "size": 1500}],
            "spread": 0.02
        }

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
