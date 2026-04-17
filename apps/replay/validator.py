"""
Replay 可交易校验。
"""

from __future__ import annotations

from apps.replay.loader import ReplayInput


def validate_replay_input(item: ReplayInput) -> tuple[bool, str | None]:
    reasons: list[str] = []

    if item.thesis is None:
        reasons.append("missing_thesis_history")
    if item.risk is None:
        reasons.append("missing_risk_history")
    if item.sizing is None:
        reasons.append("missing_sizing_history")
    if item.order.polymarket_condition_id is None:
        reasons.append("missing_condition_id")
    if item.order.size <= 0:
        reasons.append("non_positive_order_size")
    if item.risk is not None and not item.risk.allow:
        reasons.append("risk_blocked")
    if item.snapshot is None:
        reasons.append("missing_entry_snapshot")
    if item.resolution is None:
        reasons.append("missing_market_resolution")

    if reasons:
        return False, ",".join(reasons)
    return True, None
