"""
Replay 服务。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from apps.replay.executor import try_fill_order
from apps.replay.exporter import export_replay_artifacts
from apps.replay.loader import load_replay_inputs
from apps.replay.metrics import build_equity_curve, summarize_run
from apps.replay.settlement import settle_trade
from apps.replay.validator import validate_replay_input
from libs.models.db_models import (
    ReplayCandidateResult as ReplayCandidateResultModel,
    ReplayEquityPoint,
    ReplayRun,
    ReplayTradeResult as ReplayTradeResultModel,
)
from libs.models.schemas import (
    ReplayCandidateResult,
    ReplayRunSummary,
    ReplayTradeResult,
)


class ReplayService:
    """按历史数据执行候选单回放。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run(
        self,
        *,
        start: datetime,
        end: datetime,
        export_root: Path | None,
    ) -> ReplayRunSummary:
        run = ReplayRun(
            start_at=start,
            end_at=end,
            window_anchor="published_at",
            status="running",
        )
        self._session.add(run)
        await self._session.flush()

        candidate_rows: list[ReplayCandidateResultModel] = []
        trade_rows: list[ReplayTradeResultModel] = []

        for item in await load_replay_inputs(self._session, start=start, end=end):
            tradable, reason = validate_replay_input(item)
            candidate_row = ReplayCandidateResultModel(
                replay_run_id=run.id,
                candidate_order_id=item.order.id,
                event_id=item.event.event_id,
                condition_id=item.order.polymarket_condition_id,
                side=item.order.side,
                outcome=item.order.outcome,
                target_price=item.order.target_price,
                order_size=item.order.size,
                is_tradable=tradable,
                was_filled=False,
                net_edge=item.sizing.edge_net if item.sizing is not None else None,
                not_tradable_reason=reason,
            )
            self._session.add(candidate_row)
            await self._session.flush()
            await self._session.refresh(candidate_row)
            candidate_rows.append(candidate_row)

            if not tradable:
                continue

            fill, fill_reason = try_fill_order(item)
            if fill is None:
                candidate_row.not_filled_reason = fill_reason
                await self._session.flush()
                await self._session.refresh(candidate_row)
                continue

            candidate_row.was_filled = True
            candidate_row.fill_price = fill.fill_price
            candidate_row.fill_size = fill.fill_size
            candidate_row.fill_at = fill.fill_at
            await self._session.flush()
            await self._session.refresh(candidate_row)

            settlement = settle_trade(item, fill)
            trade_row = ReplayTradeResultModel(
                replay_run_id=run.id,
                candidate_result_id=candidate_row.id,
                candidate_order_id=item.order.id,
                condition_id=item.order.polymarket_condition_id or "",
                side=item.order.side,
                outcome=item.order.outcome,
                fill_at=fill.fill_at,
                fill_price=fill.fill_price,
                fill_size=fill.fill_size,
                resolved_at=settlement.resolved_at,
                resolved_outcome=settlement.resolved_outcome,
                payout_per_share=settlement.payout_per_share,
                pnl=settlement.pnl,
                holding_minutes=settlement.holding_minutes,
                is_win=settlement.is_win,
            )
            self._session.add(trade_row)
            await self._session.flush()
            await self._session.refresh(trade_row)
            trade_rows.append(trade_row)

        equity_points = build_equity_curve(trade_rows)
        for point in equity_points:
            self._session.add(
                ReplayEquityPoint(
                    replay_run_id=run.id,
                    timestamp=point.timestamp,
                    cumulative_pnl=point.cumulative_pnl,
                    drawdown=point.drawdown,
                )
            )
        await self._session.flush()

        summary_values = summarize_run(candidate_rows, trade_rows, equity_points)
        run.status = "completed"
        run.candidate_count = int(summary_values["candidate_count"])
        run.tradable_count = int(summary_values["tradable_count"])
        run.avg_net_edge = float(summary_values["avg_net_edge"])
        run.simulated_fill_count = int(summary_values["simulated_fill_count"])
        run.win_rate = float(summary_values["win_rate"])
        run.avg_holding_minutes = float(summary_values["avg_holding_minutes"])
        run.max_drawdown = float(summary_values["max_drawdown"])
        run.cumulative_pnl = float(summary_values["cumulative_pnl"])
        await self._session.flush()
        await self._session.refresh(run)

        summary_schema = ReplayRunSummary.model_validate(run)
        candidate_schemas = [
            ReplayCandidateResult.model_validate(row) for row in candidate_rows
        ]
        trade_schemas = [ReplayTradeResult.model_validate(row) for row in trade_rows]
        equity_dicts = [
            {
                "timestamp": point.timestamp,
                "cumulative_pnl": point.cumulative_pnl,
                "drawdown": point.drawdown,
            }
            for point in equity_points
        ]

        if export_root is not None:
            manifest = export_replay_artifacts(
                summary_schema,
                candidate_schemas,
                trade_schemas,
                equity_dicts,
                export_root=export_root,
            )
            run.export_dir = manifest.export_dir
            await self._session.flush()
            await self._session.refresh(run)
            summary_schema = ReplayRunSummary.model_validate(run)

        return summary_schema
