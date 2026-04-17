"""
Thesis 业务服务。

职责：
1. 汇总事件信息、市场数据、历史走势
2. 生成可读的交易论点摘要
3. 附带关键假设和风险因素
"""

from __future__ import annotations

import logging
import uuid
from typing import Any
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import ThesisHistory
from libs.models.schemas import ThesisResult

logger = logging.getLogger(__name__)


class ThesisProvider(ABC):
    """Thesis 提供者接口，支持不同的底层模型或计算逻辑。"""

    @abstractmethod
    async def build_thesis(self, candidate_id: uuid.UUID) -> ThesisResult:
        """为指定的候选单生成对应的投研结论。"""
        pass


class MockThesisProvider(ThesisProvider):
    """用于开发与测试的稳定数据返回供给者。"""

    async def build_thesis(self, candidate_id: uuid.UUID) -> ThesisResult:
        logger.info("MockThesisProvider.build_thesis: candidate_id=%s", candidate_id)
        return ThesisResult(
            candidate_id=candidate_id,
            direction="YES",
            p_market=0.45,
            q_raw=0.60,
            novelty_score=85.0,
            rule_clarity_score=90.0,
            pricing_dislocation_score=70.0,
            confidence=0.8,
            max_hold_minutes=1440,
            reasoning_summary="Mocked solid thesis because p_market is substantially lower than q_raw.",
            evidence=["News article A indicates probability > 50%", "Historical base rate is 65%"]
        )


class ThesisService:
    """操作层：封装 Provider 提供统一入口。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._provider: ThesisProvider = MockThesisProvider()

    async def generate(self, candidate_id: uuid.UUID) -> ThesisResult:
        """
        生成结构化投研结果。
        """
        result = await self._provider.build_thesis(candidate_id)
        self._session.add(
            ThesisHistory(
                candidate_id=result.candidate_id,
                direction=result.direction,
                p_market=result.p_market,
                q_raw=result.q_raw,
                novelty_score=result.novelty_score,
                rule_clarity_score=result.rule_clarity_score,
                pricing_dislocation_score=result.pricing_dislocation_score,
                confidence=result.confidence,
                max_hold_minutes=result.max_hold_minutes,
                reasoning_summary=result.reasoning_summary,
                evidence=result.evidence,
            )
        )
        await self._session.flush()
        return result
