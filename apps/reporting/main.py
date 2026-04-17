"""
Reporting 路由端点。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from apps.reporting.service import ReportingService
from libs.models.schemas import DailyReport
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting - 报表与对账"])

@router.get("/daily", summary="获取今日概览日结数据", response_model=DailyReport)
async def get_daily_report(session: AsyncSession = Depends(async_session_dependency)) -> Any:
    service = ReportingService(session)
    return await service.generate_daily_report()
