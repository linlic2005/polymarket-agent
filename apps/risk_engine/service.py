"""
Risk Engine 业务服务。

职责：
1. 加载风控限制配置
2. 校验单笔限额、组合敞口、频率限制、临期限制、盘面深度等
3. 输出 RiskDecision
"""

from __future__ import annotations

import inspect
import logging
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import RiskHistory
from libs.models.schemas import RiskDecision
from libs.utils.yaml_loader import load_risk_limits

logger = logging.getLogger(__name__)


class RiskEngineService:
    """风控引擎服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._limits = load_risk_limits()

    async def check(self, candidate_id: uuid.UUID, payload: dict[str, Any]) -> RiskDecision:
        """
        对候选单执行全量确定性风控检查。
        """
        reasons: list[str] = []
        metrics: dict[str, Any] = {}

        # load limits
        allowed_markets = self._limits.get("allowed_markets", [])
        max_risk_per_market = self._limits.get("max_risk_per_market_usd", 1000.0)
        max_risk_per_theme = self._limits.get("max_risk_per_theme_usd", 3000.0)
        max_daily_new_risk = self._limits.get("max_daily_new_risk_usd", 5000.0)
        max_daily_loss = self._limits.get("max_daily_loss_usd", 500.0)
        min_ob_depth = self._limits.get("min_orderbook_depth_usd", 100.0)
        max_spread = self._limits.get("max_spread_pct", 0.1)
        max_slippage = self._limits.get("max_estimated_slippage_pct", 0.05)
        max_hold_minutes = self._limits.get("max_hold_minutes", 10080)
        near_expiry_hours = self._limits.get("near_expiry_hours_limit", 24)

        # payload parsing
        market_name = payload.get("market_name", "unknown")
        market_risk = payload.get("current_market_risk_usd", 0.0)
        theme_risk = payload.get("current_theme_risk_usd", 0.0)
        daily_new_risk = payload.get("daily_new_risk_usd", 0.0)
        daily_loss = payload.get("daily_loss_usd", 0.0)
        ob_depth = payload.get("orderbook_depth_usd", 0.0)
        spread = payload.get("spread_pct", 0.0)
        slippage = payload.get("estimated_slippage_pct", 0.0)
        hold_minutes = payload.get("expected_hold_minutes", 0)
        hours_to_expiry = payload.get("hours_to_expiry", 999.0)
        order_risk = payload.get("order_risk_usd", 0.0)

        # 1. 白名单市场限制
        if market_name not in allowed_markets:
            reasons.append(f"Market '{market_name}' not in allowed list.")
            
        # 2. 单市场最大风险
        if market_risk + order_risk > max_risk_per_market:
            reasons.append(f"Market risk {market_risk + order_risk} exceeds limit {max_risk_per_market}.")
            
        # 3. 单主题最大风险
        if theme_risk + order_risk > max_risk_per_theme:
            reasons.append(f"Theme risk {theme_risk + order_risk} exceeds limit {max_risk_per_theme}.")
            
        # 4. 单日新增风险上限
        if daily_new_risk + order_risk > max_daily_new_risk:
            reasons.append(f"Daily new risk {daily_new_risk + order_risk} exceeds limit {max_daily_new_risk}.")
            
        # 5. 单日最大亏损
        if daily_loss > max_daily_loss:
            reasons.append(f"Daily loss {daily_loss} exceeds limits {max_daily_loss}.")
            
        # 6. 最小盘口深度
        if ob_depth < min_ob_depth:
            reasons.append(f"Orderbook depth {ob_depth} below minimum {min_ob_depth}.")
            
        # 7. 最大 spread
        if spread > max_spread:
            reasons.append(f"Spread {spread} exceeds max {max_spread}.")
            
        # 8. 最大预估滑点
        if slippage > max_slippage:
            reasons.append(f"Slippage {slippage} exceeds max {max_slippage}.")
            
        # 9. 最大持仓时长
        if hold_minutes > max_hold_minutes:
            reasons.append(f"Hold time {hold_minutes}m exceeds max {max_hold_minutes}m.")
            
        # 10. near-expiry 限制
        if hours_to_expiry < near_expiry_hours:
            reasons.append(f"Expiry within {hours_to_expiry}h violates {near_expiry_hours}h limit.")

        metrics = {
            "order_risk": order_risk,
            "theme_risk_post": theme_risk + order_risk,
            "market_risk_post": market_risk + order_risk,
            "spread": spread,
            "slippage": slippage,
            "ob_depth": ob_depth,
            "hours_to_expiry": hours_to_expiry,
        }

        allow = len(reasons) == 0

        logger.info("risk_check: candidate_id=%s allow=%s reasons=%s", candidate_id, allow, reasons)
        decision = RiskDecision(allow=allow, reason_codes=reasons, risk_metrics_json=metrics)
        if hasattr(self._session, "add"):
            self._session.add(
                RiskHistory(
                    candidate_id=candidate_id,
                    allow=decision.allow,
                    reason_codes=decision.reason_codes,
                    risk_metrics_json=decision.risk_metrics_json,
                )
            )
            flush = getattr(self._session, "flush", None)
            if flush is not None:
                flush_result = flush()
                if inspect.isawaitable(flush_result):
                    await flush_result
        return decision

    def get_current_limits(self) -> dict[str, Any]:
        """返回当前生效的风控限额。"""
        return self._limits
