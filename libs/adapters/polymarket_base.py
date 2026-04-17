"""
Polymarket SDK 官方适配器抽象层。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PolymarketBaseAdapter(ABC):
    """Polymarket 客户端通用操作接口。"""

    @abstractmethod
    def create_or_derive_api_creds(self) -> None:
        """从私钥自动推导或生成 L2 交易证书（如 CLOB API Keys）。"""
        pass

    @abstractmethod
    async def get_markets(self) -> list[dict[str, Any]]:
        """获取所有核心市场列表。"""
        pass

    @abstractmethod
    async def get_orderbook(self, token_id: str) -> dict[str, Any]:
        """获取指环代币的 Orderbook 深度。"""
        pass

    @abstractmethod
    async def get_spread(self, token_id: str) -> float:
        """获取指定代币的市场价差。"""
        pass

    @abstractmethod
    async def place_limit_order(
        self, token_id: str, price: float, size: float, side: str
    ) -> dict[str, Any]:
        """
        发起限价单（默认 maker-first）。
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """撤销处于 Open 状态的挂单。"""
        pass

    @abstractmethod
    async def get_open_orders(self) -> list[dict[str, Any]]:
        """获取账户当前所有的挂单。"""
        pass

    @abstractmethod
    async def get_positions(self) -> list[dict[str, Any]]:
        """获取现有持仓信息。"""
        pass
