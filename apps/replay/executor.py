"""
Replay 历史盘口撮合。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.replay.loader import ReplayInput


@dataclass(slots=True)
class FillResult:
    fill_price: float
    fill_size: float
    fill_at: datetime


def try_fill_order(item: ReplayInput) -> tuple[FillResult | None, str | None]:
    snapshot = item.snapshot
    if snapshot is None:
        return None, "missing_entry_snapshot"

    if item.order.size > snapshot.executable_size:
        return None, "insufficient_executable_size"

    if item.order.side == "BUY":
        fill_price = snapshot.best_ask
        if fill_price > item.order.target_price:
            return None, "target_price_not_crossed"
    else:
        fill_price = snapshot.best_bid
        if fill_price < item.order.target_price:
            return None, "target_price_not_crossed"

    return (
        FillResult(
            fill_price=fill_price,
            fill_size=item.order.size,
            fill_at=snapshot.snapshot_at,
        ),
        None,
    )
