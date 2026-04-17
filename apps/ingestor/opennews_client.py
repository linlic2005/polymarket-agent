"""
OpenNews 业务级客户端。

封装 libs.adapters.opennews_client.OpenNewsAdapter 的低层调用，
提供面向 ingestor 服务层的业务接口。

通过依赖注入 adapter，便于测试时 mock 外部调用。
"""

from __future__ import annotations

import logging
from typing import Any

from libs.adapters.opennews_client import OpenNewsAdapter, OpenNewsAdapterBase

logger = logging.getLogger(__name__)


class OpenNewsBusinessClient:
    """
    面向 ingestor 服务层的 OpenNews 业务客户端。

    职责：
    - 调用 adapter 拉取事件
    - 校验 webhook payload 基本格式
    - 不做标准化（由 normalizer 负责）
    """

    def __init__(self, adapter: OpenNewsAdapterBase | None = None) -> None:
        """
        Args:
            adapter: OpenNews HTTP 适配器实例。
                     为 None 时自动创建默认实例，测试时可注入 mock。
        """
        self._adapter = adapter or OpenNewsAdapter()

    async def pull_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        拉取最近的事件列表。

        Args:
            limit: 最大拉取数量

        Returns:
            原始事件 dict 列表
        """
        try:
            events = await self._adapter.fetch_recent_events(limit=limit)
            logger.info("[OpenNewsBusinessClient] 拉取到 %d 条事件", len(events))
            return events
        except Exception:
            logger.exception("[OpenNewsBusinessClient] 拉取事件失败")
            raise

    def validate_webhook_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        校验 webhook payload 的基本结构。

        当前校验：
        - 必须包含 'id' 字段
        - 必须包含 'title' 字段

        Args:
            payload: 原始 webhook JSON

        Returns:
            校验通过的 payload（原样返回）

        Raises:
            ValueError: 校验失败时抛出
        """
        if not payload.get("id"):
            raise ValueError("Webhook payload 缺少 'id' 字段")
        if not payload.get("title"):
            raise ValueError("Webhook payload 缺少 'title' 字段")
        return payload

    async def close(self) -> None:
        """关闭底层适配器连接。"""
        await self._adapter.close()
