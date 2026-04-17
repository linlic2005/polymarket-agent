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

    async def get_event_rules(self, event_slug: str) -> str:
        """
        根据 event slug 获取详细的 rule_text，通常包含判定源、过期细节等。

        Args:
            event_slug: 事件 Slug

        Returns:
            解析出的规则文本字符串
        """
        logger.info("[PolymarketMarketClient] get_event_rules(event_slug=%r)", event_slug)

        # GET /events/{slug}
        data = await self._safe_get(f"/events/{event_slug}")

        if data is None:
            logger.warning("[PolymarketMarketClient] Failed to fetch event %s, returning default rules", event_slug)
            return "Rules details: Unable to fetch event rules from API."

        # Extract rule_text from the event data
        rule_text = data.get("rule_text", "") or data.get("description", "")
        if not rule_text:
            # Try to construct from available fields
            question = data.get("question", "Unknown question")
            start_date = data.get("start_date", "")
            end_date = data.get("end_date", "")
            rule_text = f"Question: {question}. "
            if start_date:
                rule_text += f"Starts: {start_date}. "
            if end_date:
                rule_text += f"Ends: {end_date}. "
            if not start_date and not end_date:
                rule_text = f"Rules details: If resolution source reports YES before the market expires, resolves to YES. Otherwise NO."

        return rule_text

    async def get_market_orderbook(self, token_id: str) -> dict[str, Any]:
        """
        获取指定 token (Outcome) 的 Orderbook。

        Args:
            token_id: Outcome Token ID (如 YES 的 tokenId)

        Returns:
            Orderbook字典，包含bids、asks等
        """
        logger.info("[PolymarketMarketClient] get_market_orderbook(token_id=%r)", token_id)

        # GET /markets/{token_id} which includes order_book
        data = await self._safe_get(f"/markets/{token_id}")

        if data is None:
            logger.warning("[PolymarketMarketClient] Failed to fetch market %s, returning empty orderbook", token_id)
            return {"bids": [], "asks": [], "spread": 0.0}

        order_book = data.get("order_book", {})
        if not order_book:
            return {"bids": [], "asks": [], "spread": 0.0}

        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])

        # Calculate spread if possible
        spread = 0.0
        if bids and asks:
            best_bid = float(bids[0].get("price", 0)) if bids else 0.0
            best_ask = float(asks[0].get("price", 0)) if asks else 0.0
            spread = best_ask - best_bid

        return {
            "bids": bids,
            "asks": asks,
            "spread": spread
        }

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
