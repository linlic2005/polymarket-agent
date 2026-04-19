"""
Polymarket Market Data API Client.

封装了针对 Polymarket 市场信息 (Gamma API) 的查询逻辑。
用于 mapper 模块搜索市场以及 rules/execution 模块查询市场最新快照。
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

    async def _safe_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Make a safe GET request with error handling."""
        try:
            client = await self._get_http()
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("[PolymarketMarketClient] HTTP error %s: %s", e.response.status_code, e.response.text)
            return None
        except httpx.RequestError as e:
            logger.error("[PolymarketMarketClient] Request error: %s", str(e))
            return None
        except Exception as e:
            logger.error("[PolymarketMarketClient] Unexpected error: %s", str(e))
            return None

    async def search_events(self, query: str) -> list[dict[str, Any]]:
        """
        根据指定条件搜索聚合事件(events)。

        Args:
            query: 搜索关键词

        Returns:
            市场事件字典的列表
        """
        if not query:
            return []

        logger.info("[PolymarketMarketClient] search_events(query=%r)", query)

        # GET /events?active=true&closed=false
        data = await self._safe_get("/events", params={"active": "true", "closed": "false"})

        if data is None:
            logger.warning("[PolymarketMarketClient] Failed to fetch events, returning empty list")
            return []

        # Filter events matching the query in title or slug
        query_lower = query.lower()
        matching_events = []
        for event in data:
            event_title = event.get("title", "") or ""
            event_slug = event.get("slug", "") or ""
            if query_lower in event_title.lower() or query_lower in event_slug.lower():
                # Fetch markets for each event
                slug = event.get("slug")
                if slug:
                    markets_data = await self._safe_get("/markets", params={"event": slug})
                    event["markets"] = markets_data if markets_data else []
                matching_events.append(event)

        logger.info("[PolymarketMarketClient] Found %d matching events", len(matching_events))
        return matching_events

    async def get_event_rules(self, market_id: str) -> str:
        """
        根据 market id 获取详细的 rule_text（description），包含判定源、过期细节等。

        Polymarket 的 /markets/{id} 端点返回完整的 description 字段，
        其中包含 resolution source 和结束条件。

        Args:
            market_id: 市场 ID（Polymarket 数字 ID，非 condition_id）

        Returns:
            规则文本字符串
        """
        logger.info("[PolymarketMarketClient] get_event_rules(market_id=%r)", market_id)

        # GET /markets/{id}  — 返回单个市场的完整描述（含 resolution source）
        data = await self._safe_get(f"/markets/{market_id}")

        # _safe_get 返回 None / dict，但 /markets/{id} 返回 [list] 需要特殊处理
        # 实际返回是 list[dict]，_safe_get 不认识会走异常分支
        # 改用直接调用
        try:
            client = await self._get_http()
            response = await client.get(f"/markets/{market_id}")
            response.raise_for_status()
            result = response.json()
            # markets endpoint 返回 list
            if isinstance(result, list):
                data = result[0] if result else {}
            elif isinstance(result, dict):
                data = result
            else:
                data = {}
        except Exception:
            logger.warning("[PolymarketMarketClient] Failed to fetch market %s", market_id)
            return "Rules details: Unable to fetch event rules from API."

        if not data:
            return "Rules details: Unable to fetch event rules from API."

        # Extract description as rule_text
        rule_text = data.get("description", "") or data.get("question", "")
        if not rule_text:
            rule_text = "Rules details: No description available for this market."

        return rule_text

    async def get_market_orderbook(self, market_id: str) -> dict[str, Any]:
        """
        获取指定市场的订单簿快照。

        Polymarket 的 /markets/{id} 返回完整市场数据，其中：
        - bestBid / bestAsk: 当前最优买卖价
        - spread: 买卖价差
        - order_book.bids / order_book.asks: 完整档口（如果有）

        Args:
            market_id: Polymarket 市场数字 ID

        Returns:
            包含 bids、asks、spread 的字典
        """
        logger.info("[PolymarketMarketClient] get_market_orderbook(market_id=%r)", market_id)

        try:
            client = await self._get_http()
            response = await client.get(f"/markets/{market_id}")
            response.raise_for_status()
            result = response.json()
            # markets endpoint 返回 list
            if isinstance(result, list):
                data = result[0] if result else {}
            elif isinstance(result, dict):
                data = result
            else:
                data = {}
        except Exception:
            logger.warning("[PolymarketMarketClient] Failed to fetch market %s", market_id)
            return {"bids": [], "asks": [], "spread": 0.0, "best_bid": None, "best_ask": None}

        best_bid = data.get("bestBid")
        best_ask = data.get("bestAsk")
        spread = data.get("spread", 0.0)

        # Try nested order_book for full depth
        order_book = data.get("order_book", {}) or {}
        bids = order_book.get("bids", []) if isinstance(order_book, dict) else []
        asks = order_book.get("asks", []) if isinstance(order_book, dict) else []

        # If no nested book, fall back to top-level prices
        if not bids and best_bid is not None:
            bids = [{"price": best_bid, "size": None}]
        if not asks and best_ask is not None:
            asks = [{"price": best_ask, "size": None}]

        return {
            "bids": bids,
            "asks": asks,
            "spread": float(spread) if spread else 0.0,
            "best_bid": float(best_bid) if best_bid is not None else None,
            "best_ask": float(best_ask) if best_ask is not None else None,
        }

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
