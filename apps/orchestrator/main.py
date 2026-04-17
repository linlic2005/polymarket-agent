"""
Orchestrator 对外调度流转接口。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.orchestrator.service import OrchestratorService
from libs.models.schemas import ApprovalDecision
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/orchestrator", tags=["Orchestrator - 流程编排"])

@router.post("/run/{event_id}", summary="启动单向管线评估")
async def run_pipeline(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """触发新事件的工作流管道。"""
    service = OrchestratorService(session)
    return await service.run_pipeline(event_id)

@router.post("/approve/{candidate_id}", summary="注入表单的审批决策")
async def approve_candidate(
    candidate_id: uuid.UUID,
    decision: ApprovalDecision,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """对处于 AWAIT_APPROVAL 状态的单子进行拍板裁断，触发底层执行网络。"""
    if candidate_id != decision.candidate_id:
         raise ValueError("Path ID and body ID mismatch.")
    
    service = OrchestratorService(session)
    return await service.process_approval(decision)
