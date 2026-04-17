"""
Sizing 业务服务。

职责：
1. 根据配置计算净边际（Net Edge）
2. 应用半凯利公式 (Half Kelly) 并按上限裁剪
3. 输出 SizingDecision
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import SizingHistory
from libs.models.schemas import SizingDecision
from libs.utils.yaml_loader import load_sizing_config

logger = logging.getLogger(__name__)


class SizingService:
    """仓位计算服务。"""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session
        self._config = load_sizing_config()

    def calculate(
        self,
        candidate_id: uuid.UUID,
        p_market: float,
        q_raw: float,
        bankroll_override: float | None = None,
    ) -> SizingDecision:
        """
        基于净边际（Net Edge）的半凯利标准计算仓位。

        公式：
        q_adj = p_market + alpha * (q_raw - p_market)
        p_eff = p_market + taker_fee + slippage + exit_cost + uncertainty
        edge_net = q_adj - p_eff
        if edge_net <= 0: f_full = f_half = f_final = 0
        else:
           f_full = (q_adj - p_eff) / (1 - p_eff)
           f_half = 0.5 * f_full
        
        f_final = min(f_half, max_position_limit / bankroll)
        """
        alpha = self._config.get("alpha", 0.5)
        taker_fee = self._config.get("taker_fee_per_share", 0.01)
        slippage = self._config.get("expected_slippage_per_share", 0.01)
        exit_cost = self._config.get("exit_cost_reserve", 0.01)
        uncertainty = self._config.get("uncertainty_haircut", 0.02)
        bankroll = bankroll_override or self._config.get("bankroll_usd", 10000.0)
        max_position_size = self._config.get("max_position_size_usd", 500.0)

        q_adj = p_market + alpha * (q_raw - p_market)
        p_eff = p_market + taker_fee + slippage + exit_cost + uncertainty
        edge_net = q_adj - p_eff

        sizing_reasons = []

        if edge_net <= 0:
            f_full = 0.0
            f_half = 0.0
            f_final = 0.0
            sizing_reasons.append("Net edge is zero or negative.")
        else:
            f_full = edge_net / (1.0 - p_eff) if p_eff < 1.0 else 0.0
            f_half = 0.5 * f_full
            # bankroll limit based f_limit
            max_f = max_position_size / bankroll if bankroll > 0 else 0.0
            f_final = min(f_half, max_f)
            
            if f_final == max_f:
                sizing_reasons.append(f"Position capped by max limit of {max_position_size} USD.")

        logger.info(
            "sizing.calculate: id=%s p_market=%.3f q_raw=%.3f p_eff=%.3f q_adj=%.3f edge_net=%.3f f_final=%.4f",
            candidate_id, p_market, q_raw, p_eff, q_adj, edge_net, f_final
        )

        decision = SizingDecision(
            candidate_id=candidate_id,
            p_market=p_market,
            q_raw=q_raw,
            alpha=alpha,
            q_adj=q_adj,
            taker_fee_per_share=taker_fee,
            expected_slippage_per_share=slippage,
            exit_cost_reserve=exit_cost,
            uncertainty_haircut=uncertainty,
            p_eff=p_eff,
            edge_net=edge_net,
            f_full=f_full,
            f_half=f_half,
            f_final=f_final,
            sizing_reason_codes=sizing_reasons
        )
        if self._session is not None:
            self._session.add(
                SizingHistory(
                    candidate_id=decision.candidate_id,
                    p_market=decision.p_market,
                    q_raw=decision.q_raw,
                    alpha=decision.alpha,
                    q_adj=decision.q_adj,
                    taker_fee_per_share=decision.taker_fee_per_share,
                    expected_slippage_per_share=decision.expected_slippage_per_share,
                    exit_cost_reserve=decision.exit_cost_reserve,
                    uncertainty_haircut=decision.uncertainty_haircut,
                    p_eff=decision.p_eff,
                    edge_net=decision.edge_net,
                    f_full=decision.f_full,
                    f_half=decision.f_half,
                    f_final=decision.f_final,
                    sizing_reason_codes=decision.sizing_reason_codes,
                )
            )
        return decision
