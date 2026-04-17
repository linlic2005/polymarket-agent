"""
Thesis 模块路由。

负责生成和管理交易论点（为什么要做这笔交易）。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.thesis.service import ThesisService
from libs.models.schemas import ThesisResult
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/thesis", tags=["Thesis - 交易论点"])


@router.post("/build/{candidate_id}", response_model=ThesisResult, summary="为候选单生成交易论点")
async def build_thesis(
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(async_session_dependency),
) -> ThesisResult:
    """基于候选相关上下文生成结构化交易论点结果。"""
    service = ThesisService(session)
    return await service.generate(candidate_id)
