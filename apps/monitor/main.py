"""
Monitor Endpoint。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from apps.monitor.service import MonitorService
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/monitor", tags=["Monitor - 监控面板"])

@router.post("/scan", summary="触发一次扫描与极速检查规则退出")
async def manual_scan(session: AsyncSession = Depends(async_session_dependency)) -> dict[str, Any]:
     service = MonitorService(session)
     return await service.scan_and_trigger_exits()