"""
Hermes Orchestration 集成层适配器。

用于与外部 Hermes 编排引擎通信，实现跨系统工作流协调。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from libs.models.settings import get_settings

logger = logging.getLogger(__name__)


class HermesClient:
    """
    Hermes 编排引擎客户端。

    预留接口 —— 待 Hermes 协议确认后填充实现。
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._endpoint = self._settings.hermes_endpoint
        self._api_key = self._settings.hermes_api_key
        self._http: httpx.AsyncClient | None = None

    async def _get_http(self) -> httpx.AsyncClient:
        """懒初始化 HTTP 客户端。"""
        if self._http is None or self._http.is_closed:
            headers: dict[str, str] = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._http = httpx.AsyncClient(
                base_url=self._endpoint,
                headers=headers,
                timeout=30.0,
            )
        return self._http

    async def notify_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        """
        向 Hermes 发送事件通知。

        Args:
            event_type: 事件类型标识
            payload: 事件负载

        Returns:
            是否发送成功
        """
        if not self._endpoint:
            logger.debug("[HermesClient] endpoint 未配置，跳过通知")
            return False

        # TODO: 实际 HTTP 调用
        logger.info("[HermesClient] notify_event type=%s (stub)", event_type)
        return False

    async def fetch_workflow_state(self, workflow_id: str) -> dict[str, Any]:
        """查询编排工作流状态。"""
        if not self._endpoint:
            return {"status": "not_configured"}
        # TODO: 实际实现
        return {"workflow_id": workflow_id, "status": "stub"}

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
