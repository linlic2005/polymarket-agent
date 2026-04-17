"""
Polymarket Paper Trading Emulator.
基于内存状态网格，实现在隔离空间的模拟撮合（保证 Dry Run 完备可用）。
"""

import logging
import uuid
from typing import Any

from libs.adapters.polymarket_base import PolymarketBaseAdapter

logger = logging.getLogger(__name__)


class PolymarketPaperAdapter(PolymarketBaseAdapter):
    def __init__(self) -> None:
        self.orders: dict[str, dict[str, Any]] = {}
        self.positions: dict[str, float] = {}

    def create_or_derive_api_creds(self) -> None:
        logger.info("[PaperAdapter] API creds bypass for paper trading mode.")

    async def get_markets(self) -> list[dict[str, Any]]:
        return []

    async def get_orderbook(self, token_id: str) -> dict[str, Any]:
        return {
            "bids": [{"price": 0.5, "size": 1000}],
            "asks": [{"price": 0.51, "size": 1000}]
        }

    async def get_spread(self, token_id: str) -> float:
        return 0.01

    async def place_limit_order(
        self, token_id: str, price: float, size: float, side: str
    ) -> dict[str, Any]:
        order_id = str(uuid.uuid4())
        logger.info(
            "[PaperAdapter] Placed limit order [%s] for %s @ %.4f, size %.2f. Faking fill automatically.",
            side, token_id, price, size
        )

        self.orders[order_id] = {
            "id": order_id,
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
            "status": "FILLED",
            "filled_size": size
        }

        pos_key = f"{token_id}_{side}"
        self.positions[pos_key] = self.positions.get(pos_key, 0.0) + size

        return {
            "id": order_id,
            "status": "FILLED",
            "filled_size": size
        }

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id]["status"] = "CANCELLED"
            logger.info("[PaperAdapter] Cancelled order %s", order_id)
            return True
        return False

    async def get_open_orders(self) -> list[dict[str, Any]]:
        return [
            o for o in self.orders.values()
            if o.get("status") not in ["FILLED", "CANCELLED", "REJECTED"]
        ]

    async def get_positions(self) -> list[dict[str, Any]]:
        return [
            {"token_id": k.split("_")[0], "side": k.split("_")[1], "amount": v}
            for k, v in self.positions.items()
        ]
