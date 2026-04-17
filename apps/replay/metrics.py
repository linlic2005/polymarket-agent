"""
Replay 指标聚合。
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.models.db_models import ReplayCandidateResult, ReplayTradeResult


@dataclass(slots=True)
class EquityPoint:
    timestamp: object
    cumulative_pnl: float
    drawdown: float


def build_equity_curve(trades: list[ReplayTradeResult]) -> list[EquityPoint]:
    cumulative = 0.0
    peak = 0.0
    points: list[EquityPoint] = []

    for trade in sorted(trades, key=lambda row: row.resolved_at):
        cumulative += trade.pnl
        peak = max(peak, cumulative)
        drawdown = peak - cumulative
        points.append(
            EquityPoint(
                timestamp=trade.resolved_at,
                cumulative_pnl=cumulative,
                drawdown=drawdown,
            )
        )

    return points


def summarize_run(
    candidate_results: list[ReplayCandidateResult],
    trades: list[ReplayTradeResult],
    equity_points: list[EquityPoint],
) -> dict[str, float | int]:
    tradable = [row for row in candidate_results if row.is_tradable]
    settled_trades = trades

    avg_net_edge = (
        sum((row.net_edge or 0.0) for row in tradable) / len(tradable)
        if tradable
        else 0.0
    )
    win_rate = (
        sum(1 for trade in settled_trades if trade.pnl > 0) / len(settled_trades)
        if settled_trades
        else 0.0
    )
    avg_holding_minutes = (
        sum(trade.holding_minutes for trade in settled_trades) / len(settled_trades)
        if settled_trades
        else 0.0
    )
    max_drawdown = max((point.drawdown for point in equity_points), default=0.0)
    cumulative_pnl = sum(trade.pnl for trade in settled_trades)

    return {
        "candidate_count": len(candidate_results),
        "tradable_count": len(tradable),
        "avg_net_edge": avg_net_edge,
        "simulated_fill_count": len(settled_trades),
        "win_rate": win_rate,
        "avg_holding_minutes": avg_holding_minutes,
        "max_drawdown": max_drawdown,
        "cumulative_pnl": cumulative_pnl,
    }
