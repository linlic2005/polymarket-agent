"""
6551 OpenNews HTTP 适配器。

单一职责：封装 OpenNews REST API 的 HTTP 调用，返回原始 dict。
不做任何业务逻辑处理（标准化、去重等由上层 ingestor 模块负责）。

所有外部调用都在此适配器内，便于测试时整体 mock。
"""

from __future__ import annotations

import abc
import logging
from typing import Any

import httpx

from libs.models.settings import get_settings

logger = logging.getLogger(__name__)


class OpenNewsAdapterBase(abc.ABC):
    """
    OpenNews 适配器抽象基类。

    便于测试时替换为 mock 实现。
    """

    @abc.abstractmethod
    async def fetch_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """拉取最近的事件列表（原始 dict）。"""
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

    - fetch_recent_events: GET /events/recent
    - subscribe_ws: WebSocket 预留（NotImplementedError）
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
                },
                timeout=30.0,
            )
        return self._http

    async def fetch_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        拉取最近事件。

        GET /events/recent?limit={limit}

        Returns:
            原始 JSON 列表，每个元素为一个事件 dict。

        Raises:
            httpx.HTTPStatusError: 非 2xx 状态码时抛出。
        """
        http = await self._get_http()
        try:
            response = await http.get("/events/recent", params={"limit": limit})
            response.raise_for_status()
            data = response.json()
            # API 可能返回 {"events": [...]} 或直接 [...]
            if isinstance(data, dict) and "events" in data:
                return data["events"]
            if isinstance(data, list):
                return data
            logger.warning("[OpenNewsAdapter] 意外的响应格式: %s", type(data))
            return []
        except httpx.HTTPStatusError as exc:
            logger.error(
                "[OpenNewsAdapter] HTTP 错误: status=%d url=%s",
                exc.response.status_code,
                exc.request.url,
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
