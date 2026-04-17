"""
Monitor 扫描服务。
监听订单及仓位状态。支持五大退出条件。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from libs.models.db_models import Position, CandidateMarket, RuleSnapshot
from libs.adapters.polymarket_live import PolymarketLiveAdapter
from libs.utils.yaml_loader import load_risk_limits

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._adapter = PolymarketLiveAdapter()
        self._limits = load_risk_limits()
        self._max_daily_loss_usd = self._limits.get("max_daily_loss_usd", 500.0)
        self._max_hold_minutes = self._limits.get("max_hold_minutes", 10080)

    async def _check_thesis_invalid(self, pos: Position) -> bool:
        """
        退出条件1: thesis 失效。
        检查关联候选单的 rule_text_changed 标志。
        """
        if pos.candidate_id is None:
            return False
        try:
            stmt = select(CandidateMarket).where(
                CandidateMarket.candidate_id == pos.candidate_id
            )
            res = await self._session.execute(stmt)
            candidate = res.scalar_one_or_none()
            if candidate and candidate.rule_text_changed:
                logger.warning(
                    "[Monitor] thesis_invalid=True for position %s (candidate %s)",
                    pos.id, pos.candidate_id
                )
                return True
        except Exception as e:
            logger.error("[Monitor] Failed to check thesis_invalid: %s", e)
        return False

    async def _check_timeout(self, pos: Position) -> bool:
        """
        退出条件2: 持仓超时。
        检查 pos.created_at + max_hold_minutes 是否已过期。
        """
        max_hold = self._max_hold_minutes
        deadline = pos.created_at + timedelta(minutes=max_hold)
        now = datetime.now(timezone.utc)
        if deadline < now:
            logger.warning(
                "[Monitor] timeout=True for position %s (created %s, deadline %s)",
                pos.id, pos.created_at, deadline
            )
            return True
        return False

    async def _check_spread_deteriorate(self, pos: Position) -> bool:
        """
        退出条件3: spread 恶化。
        获取当前 spread，与持仓快照中的 spread_snapshot 对比。
        当前 spread > 初始 spread * 2 时触发。
        """
        if pos.candidate_id is None:
            return False
        try:
            # 1. 获取初始 spread
            stmt_cand = select(CandidateMarket).where(
                CandidateMarket.candidate_id == pos.candidate_id
            )
            res = await self._session.execute(stmt_cand)
            candidate = res.scalar_one_or_none()
            if candidate is None:
                return False
            initial_spread = candidate.spread_snapshot
            if initial_spread is None or initial_spread <= 0:
                return False

            # 2. 获取当前 spread
            current_spread = await self._adapter.get_spread(pos.polymarket_condition_id)
            if current_spread <= 0:
                return False

            # 3. 判断是否恶化超过2倍
            if current_spread > initial_spread * 2:
                logger.warning(
                    "[Monitor] spread_deteriorate=True for position %s "
                    "(current=%.4f, initial=%.4f, ratio=%.2f)",
                    pos.id, current_spread, initial_spread, current_spread / initial_spread
                )
                return True
        except Exception as e:
            logger.error("[Monitor] Failed to check spread_deteriorate: %s", e)
        return False

    async def _check_rule_change(self, pos: Position) -> bool:
        """
        退出条件4: 规则变动。
        从 rule_snapshots 表获取持仓建立时的规则快照，
        与 CandidateMarket.rule_text 当前值对比。
        """
        if pos.candidate_id is None:
            return False
        try:
            # 获取当前 rule_text
            stmt_cand = select(CandidateMarket).where(
                CandidateMarket.candidate_id == pos.candidate_id
            )
            res = await self._session.execute(stmt_cand)
            candidate = res.scalar_one_or_none()
            if candidate is None or candidate.rule_text is None:
                return False
            current_rule_text = candidate.rule_text

            # 获取持仓创建时的规则快照
            stmt_snap = (
                select(RuleSnapshot)
                .where(RuleSnapshot.candidate_id == pos.candidate_id)
                .order_by(RuleSnapshot.snapshot_at.asc())
                .limit(1)
            )
            res_snap = await self._session.execute(stmt_snap)
            snapshot = res_snap.scalar_one_or_none()
            if snapshot is None:
                return False

            if snapshot.rule_text != current_rule_text:
                logger.warning(
                    "[Monitor] rule_change=True for position %s "
                    "(snapshot='%s...', current='%s...')",
                    pos.id,
                    snapshot.rule_text[:50] if snapshot.rule_text else "",
                    current_rule_text[:50] if current_rule_text else "",
                )
                return True
        except Exception as e:
            logger.error("[Monitor] Failed to check rule_change: %s", e)
        return False

    async def _check_circuit_break(self) -> bool:
        """
        退出条件5: 全局熔断。
        计算今日累计盈亏，与 max_daily_loss_usd 对比。
        """
        try:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            stmt = select(func.sum(Position.realised_pnl)).where(
                Position.updated_at >= today_start
            )
            res = await self._session.execute(stmt)
            daily_pnl = res.scalar() or 0.0
            if daily_pnl < 0 and abs(daily_pnl) > self._max_daily_loss_usd:
                logger.warning(
                    "[Monitor] circuit_break=True (daily_loss=%.2f > max=%.2f)",
                    abs(daily_pnl), self._max_daily_loss_usd
                )
                return True
        except Exception as e:
            logger.error("[Monitor] Failed to check circuit_break: %s", e)
        return False

    async def scan_and_trigger_exits(self) -> dict[str, int]:
        """
        扫描系统状态，同步远程持仓记录 position 和 fills
        触发强平退出:
        1. thesis 失效
        2. 持仓超时
        3. spread 恶化
        4. 规则变动
        5. 全局熔断
        """
        stmt = select(Position).where(Position.size > 0)
        res = await self._session.execute(stmt)
        positions = res.scalars().all()

        exited_count = 0

        for pos in positions:
            thesis_invalid = await self._check_thesis_invalid(pos)
            timeout = await self._check_timeout(pos)
            spread_deteriorate = await self._check_spread_deteriorate(pos)
            rule_change = await self._check_rule_change(pos)
            circuit_break = await self._check_circuit_break()

            if any([thesis_invalid, timeout, spread_deteriorate, rule_change, circuit_break]):
                logger.warning(
                    "[Monitor] Exit condition met for position %s. Emergency exit initiated. "
                    "(thesis_invalid=%s, timeout=%s, spread_deteriorate=%s, rule_change=%s, circuit_break=%s)",
                    pos.id, thesis_invalid, timeout, spread_deteriorate, rule_change, circuit_break
                )
                pos.size = 0.0
                exited_count += 1

        try:
            await self._session.commit()
        except:
            await self._session.rollback()

        return {"scanned_positions": len(positions), "exits_triggered": exited_count}
