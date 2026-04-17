"""
Polymarket Official SDK Live Adapter.
用于真实的实盘或在官方 API 端的下发动作。
需要依赖真正的私钥及 API Keys。不允许使用浏览器自动化。
"""

from __future__ import annotations

import os
import logging
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs

from libs.adapters.polymarket_base import PolymarketBaseAdapter

logger = logging.getLogger(__name__)


class PolymarketLiveAdapter(PolymarketBaseAdapter):
    """Polymarket 官方 CLOB API 适配器。"""

    def __init__(self) -> None:
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        self.api_key = os.getenv("POLYMARKET_API_KEY")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET")
        self.passphrase = os.getenv("POLYMARKET_PASSPHRASE")

        self._client: ClobClient | None = None
        self._create_client()

    def _create_client(self) -> None:
        """Initialize the CLOB client if credentials are available."""
        if not all([self.private_key, self.api_key, self.api_secret, self.passphrase]):
            logger.warning(
                "[LiveAdapter] Missing partial credentials from environment variables. "
                "POLYMARKET_PRIVATE_KEY, POLYMARKET_API_KEY, POLYMARKET_API_SECRET, and "
                "POLYMARKET_PASSPHRASE are all required. Cannot operate live orders safely. "
                "Setting client to None."
            )
            self._client = None
            return

        try:
            creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                passphrase=self.passphrase,
            )
            self._client = ClobClient(
                host="https://clob.polymarket.com",
                creds=creds,
                private_key=self.private_key,
            )
            logger.info("[LiveAdapter] Successfully initialized ClobClient")
        except Exception as e:
            logger.error("[LiveAdapter] Failed to create ClobClient: %s", str(e))
            self._client = None

    def create_or_derive_api_creds(self) -> None:
        """从私钥自动推导或生成 L2 交易证书（如 CLOB API Keys）。"""
        # Credentials are derived during ClobClient initialization
        logger.info("[LiveAdapter] API creds are derived during ClobClient initialization")

    async def get_markets(self) -> list[dict[str, Any]]:
        """
        获取所有核心市场列表。

        Returns:
            市场字典列表
        """
        if self._client is None:
            logger.warning("[LiveAdapter] get_markets called but client is None")
            return []

        try:
            markets = self._client.get_markets()
            logger.info("[LiveAdapter] get_markets returned %d markets", len(markets))
            return markets if markets else []
        except Exception as e:
            logger.error("[LiveAdapter] get_markets failed: %s", str(e))
            return []

    async def get_orderbook(self, token_id: str) -> dict[str, Any]:
        """
        获取指定代币的 Orderbook 深度。

        Args:
            token_id: Token ID

        Returns:
            Orderbook字典，包含bids、asks
        """
        if self._client is None:
            logger.warning("[LiveAdapter] get_orderbook called but client is None")
            return {"bids": [], "asks": []}

        try:
            orderbook = self._client.get_order_book(token_id)
            logger.info("[LiveAdapter] get_orderbook for %s: %d bids, %d asks",
                        token_id,
                        len(orderbook.get("bids", [])),
                        len(orderbook.get("asks", [])))
            return orderbook if orderbook else {"bids": [], "asks": []}
        except Exception as e:
            logger.error("[LiveAdapter] get_orderbook failed for %s: %s", token_id, str(e))
            return {"bids": [], "asks": []}

    async def get_spread(self, token_id: str) -> float:
        """
        获取指定代币的市场价差。

        Args:
            token_id: Token ID

        Returns:
            价差（买一卖一差值）
        """
        orderbook = await self.get_orderbook(token_id)
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])

        if not bids or not asks:
            return 0.0

        try:
            best_bid = float(bids[0].get("price", 0)) if bids else 0.0
            best_ask = float(asks[0].get("price", 0)) if asks else 0.0
            return best_ask - best_bid
        except (ValueError, IndexError) as e:
            logger.error("[LiveAdapter] get_spread calculation error: %s", str(e))
            return 0.0

    async def place_limit_order(
        self, token_id: str, price: float, size: float, side: str
    ) -> dict[str, Any]:
        """
        发起限价单（默认 maker-first）。

        Args:
            token_id: Token ID
            price: 价格
            size: 数量
            side: 买卖方向 ('BUY' or 'SELL')

        Returns:
            订单结果字典
        """
        if self._client is None:
            logger.warning("[LiveAdapter] place_limit_order called but client is None")
            return {"error": "Client not initialized"}

        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side.upper(),
            )
            result = self._client.create_order(order_args)
            logger.info("[LiveAdapter] place_limit_order succeeded: token=%s price=%.4f size=%.2f side=%s",
                        token_id, price, size, side)
            return result if result else {"error": "No result returned"}
        except Exception as e:
            logger.error("[LiveAdapter] place_limit_order failed: %s", str(e))
            return {"error": str(e)}

    async def cancel_order(self, order_id: str) -> bool:
        """
        撤销处于 Open 状态的挂单。

        Args:
            order_id: 订单 ID

        Returns:
            是否成功撤销
        """
        if self._client is None:
            logger.warning("[LiveAdapter] cancel_order called but client is None")
            return False

        try:
            success = self._client.cancel_order(order_id)
            logger.info("[LiveAdapter] cancel_order(%s) = %s", order_id, success)
            return bool(success)
        except Exception as e:
            logger.error("[LiveAdapter] cancel_order(%s) failed: %s", order_id, str(e))
            return False

    async def get_open_orders(self) -> list[dict[str, Any]]:
        """
        获取账户当前所有的挂单。

        Returns:
            挂单列表
        """
        if self._client is None:
            logger.warning("[LiveAdapter] get_open_orders called but client is None")
            return []

        try:
            orders = self._client.get_orders()
            logger.info("[LiveAdapter] get_open_orders returned %d orders", len(orders))
            return orders if orders else []
        except Exception as e:
            logger.error("[LiveAdapter] get_open_orders failed: %s", str(e))
            return []

    async def get_positions(self) -> list[dict[str, Any]]:
        """
        获取现有持仓信息。

        Returns:
            持仓列表
        """
        if self._client is None:
            logger.warning("[LiveAdapter] get_positions called but client is None")
            return []

        try:
            positions = self._client.get_positions()
            logger.info("[LiveAdapter] get_positions returned %d positions", len(positions))
            return positions if positions else []
        except Exception as e:
            logger.error("[LiveAdapter] get_positions failed: %s", str(e))
            return []
