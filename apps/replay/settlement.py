"""
Replay 结算逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.replay.executor import FillResult
from apps.replay.loader import ReplayInput


@dataclass(slots=True)
class SettlementResult:
    resolved_outcome: str
    resolved_at: object
    payout_per_share: float
    pnl: float
    holding_minutes: float
    is_win: bool


def settle_trade(item: ReplayInput, fill: FillResult) -> SettlementResult:
    assert item.resolution is not None

    if item.order.outcome == "YES":
        payout = item.resolution.payout_yes
    else:
        payout = item.resolution.payout_no

    if item.order.side == "BUY":
        pnl = (payout - fill.fill_price) * fill.fill_size
    else:
        pnl = (fill.fill_price - payout) * fill.fill_size

    holding_minutes = (item.resolution.resolved_at - fill.fill_at).total_seconds() / 60.0
    return SettlementResult(
        resolved_outcome=item.resolution.resolved_outcome,
        resolved_at=item.resolution.resolved_at,
        payout_per_share=payout,
        pnl=pnl,
        holding_minutes=holding_minutes,
        is_win=pnl > 0,
    )
