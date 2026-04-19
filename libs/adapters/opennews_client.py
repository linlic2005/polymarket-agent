"""
6551 OpenNews HTTP 适配器。

单一职责：封装 OpenNews REST API 的 HTTP 调用，返回标准化后的事件列表。
不做任何业务逻辑处理（标准化、去重等由上层 ingestor 模块负责）。

API 文档：https://github.com/beare/opennews-mcp
- 基础 URL: https://ai.6551.io
- 拉取事件: POST /open/news_search
- 新闻源分类: GET /open/news_type
"""

from __future__ import annotations

import abc
import logging
import re
from typing import Any

import httpx

from libs.models.settings import get_settings

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本。"""
    return re.sub(r'<[^>]+>', '', text).strip()


class OpenNewsAdapterBase(abc.ABC):
    """
    OpenNews 适配器抽象基类。

    便于测试时替换为 mock 实现。
    """

    @abc.abstractmethod
    async def fetch_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """拉取最近的事件列表（标准化后的 dict）。"""
        ...

    @abc.abstractmethod
    async def subscribe_ws(self) -> None:
        """WebSocket 订阅（预留接口）。"""
        ...

    @abc.abstractmethod
    async def close(self) -> None:
        """关闭连接资源。"""
        ...


class OpenNewsAdapter(OpenNewsAdapterBase):
    """
    6551 OpenNews REST API 适配器。

    API:
    - POST /open/news_search  — 搜索/拉取新闻事件
    - GET  /open/news_type    — 获取新闻源分类树（预留）
    - subscribe_ws: WebSocket 预留（NotImplementedError）

    返回格式映射至 ingestor/normalizer.normalize_opennews 所需字段：
    - id          → source_event_id (str)
    - title       → 从 text HTML 去除标签得到
    - body        → "" (API 无此字段)
    - published_at → ts 字段
    - symbols      → 从 coins 列表提取 symbol
    - ai_score    → None (API 无此字段)
    - signal      → None (API 无此字段)
    - source      → source 字段保留原始值
    """

    SOURCE_ID = "opennews_6551"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = base_url or settings.opennews_base_url
        self._token = token or settings.opennews_token
        self._http: httpx.AsyncClient | None = None

    async def _get_http(self) -> httpx.AsyncClient:
        """懒初始化 HTTP 客户端。"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http

    def _transform(self, item: dict[str, Any]) -> dict[str, Any]:
        """
        将 6551 API 原始 item 转换为 normalizer 期望的格式。

        6551 API 字段:
          id, text, ts, coins, newsType, engineType, source, link, description
        目标字段 (normalize_opennews):
          id, title, body, published_at, symbols, ai_score, signal
        """
        coins = item.get("coins", []) or []
        symbols = [c["symbol"] for c in coins if c.get("symbol")]

        return {
            "id": str(item["id"]),
            "title": _strip_html(item.get("text", "")),
            "body": item.get("description", ""),
            "published_at": item.get("ts"),
            "symbols": symbols,
            "ai_score": None,
            "signal": None,
            # 额外字段，保留原始值便于调试
            "_raw_news_type": item.get("newsType"),
            "_raw_engine_type": item.get("engineType"),
            "_raw_source": item.get("source"),
            "_raw_link": item.get("link"),
        }

    async def fetch_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        拉取最近事件（POST /open/news_search）。

        Args:
            limit: 最大拉取数量

        Returns:
            标准化后的事件 dict 列表，每个元素可直接被 normalizer 处理。

        Raises:
            httpx.HTTPStatusError: 非 2xx 状态码时抛出。
        """
        http = await self._get_http()
        try:
            response = await http.post(
                "/open/news_search",
                json={"limit": limit, "page": 1},
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                logger.warning("[OpenNewsAdapter] 意外响应格式: %s", type(payload))
                return []

            items = payload.get("data") or []
            results = [self._transform(item) for item in items]
            logger.info("[OpenNewsAdapter] 拉取到 %d 条事件", len(results))
            return results

        except httpx.HTTPStatusError as exc:
            logger.error(
                "[OpenNewsAdapter] HTTP 错误: status=%d url=%s body=%s",
                exc.response.status_code,
                exc.request.url,
                exc.response.text[:200],
            )
            raise
        except Exception:
            logger.exception("[OpenNewsAdapter] fetch_recent_events 出错")
            raise

    async def subscribe_ws(self) -> None:
        """
        WebSocket 实时订阅（预留接口）。

        Raises:
            NotImplementedError: 当前版本尚未实现。
        """
        raise NotImplementedError(
            "WebSocket 订阅尚未实现，请等待后续版本。"
            f" 预留 WS URL: {get_settings().opennews_ws_url}"
        )

    async def close(self) -> None:
        """关闭 HTTP 客户端连接。"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            logger.debug("[OpenNewsAdapter] HTTP 客户端已关闭")
