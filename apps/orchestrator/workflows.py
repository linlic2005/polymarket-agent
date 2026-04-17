"""
Hermes Workflow 包装与调度接口。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HERMES_ENDPOINT = os.getenv("HERMES_ENDPOINT", "http://127.0.0.1:8642")
MAX_RETRIES = 3


class HermesWorkflowService:
    """分布式工作流引擎调度接口。"""

    def __init__(self) -> None:
        self._endpoint = HERMES_ENDPOINT
        self._http: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """懒初始化 HTTP 客户端。"""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._endpoint,
                timeout=30.0,
            )
        return self._http

    async def _post(
        self, path: str, data: dict[str, Any], retries: int = MAX_RETRIES
    ) -> bool:
        """
        通用 POST 包装器，重试 MAX_RETRIES 次。
        返回是否成功（fire-and-forget 语义）。
        """
        if not self._endpoint:
            logger.debug("[Hermes] endpoint 未配置，跳过请求: %s", path)
            return False

        client = await self._get_client()
        for attempt in range(1, retries + 1):
            try:
                resp = await client.post(path, json=data)
                if resp.status_code < 400:
                    logger.info(
                        "[Hermes] POST %s succeeded (attempt %d): %s",
                        path, attempt, resp.status_code
                    )
                    return True
                else:
                    logger.warning(
                        "[Hermes] POST %s returned %s (attempt %d/%d): %s",
                        path, resp.status_code, attempt, retries, resp.text[:200]
                    )
            except httpx.TimeoutException:
                logger.warning(
                    "[Hermes] POST %s timed out (attempt %d/%d)",
                    path, attempt, retries
                )
            except httpx.RequestError as e:
                logger.warning(
                    "[Hermes] POST %s request error (attempt %d/%d): %s",
                    path, attempt, retries, e
                )
            if attempt < retries:
                await client.aclose()
                client = await self._get_client()
        logger.warning("[Hermes] POST %s failed after %d attempts", path, retries)
        return False

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    @staticmethod
    async def notify_approval_needed(
        candidate_id: str, candidate_data: dict[str, Any]
    ) -> None:
        """
        通知流转服务此订单现状态为 AWAIT_APPROVAL，需要人为或高一级控制流裁断。
        Fire-and-forget: 失败时只记录 warning，不抛出异常。
        """
        payload = {
            "candidate_id": candidate_id,
            "status": "AWAIT_APPROVAL",
            "candidate_data": candidate_data,
        }
        svc = HermesWorkflowService()
        try:
            await svc._post("/workflow/notify", payload)
        finally:
            await svc.close()

    @staticmethod
    async def trigger_workflow(
        workflow_name: str, payload: dict[str, Any]
    ) -> None:
        """
        触发一段指定的工作流（例如：daily_report, auto_ingest）。
        Fire-and-forget: 失败时只记录 warning，不抛出异常。
        """
        full_payload = {
            "workflow_name": workflow_name,
            "payload": payload,
        }
        svc = HermesWorkflowService()
        try:
            await svc._post("/workflow/trigger", full_payload)
        finally:
            await svc.close()

    @staticmethod
    async def send_daily_report(report_data: dict[str, Any]) -> None:
        """
        发送每日汇总报告给 Hermes。
        Fire-and-forget: 失败时只记录 warning，不抛出异常。
        """
        svc = HermesWorkflowService()
        try:
            await svc._post("/workflow/report", report_data)
        finally:
            await svc.close()
