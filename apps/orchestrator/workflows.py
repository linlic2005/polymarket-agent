"""
Hermes Workflow 包装与调度接口。
"""

from typing import Any

class HermesWorkflowService:
    """预留的分布式工作流引擎调度接口。"""
    
    @staticmethod
    def trigger_workflow(workflow_name: str, payload: dict[str, Any]) -> None:
        """
        触发一段指定的工作流（例如：daily_report, auto_ingest）。
        """
        pass
        
    @staticmethod
    def notify_approval_needed(candidate_id: str, context: dict[str, Any]) -> None:
        """
        通知流转服务此订单现状态为 AWAIT_APPROVAL，需要人为或高一级控制流裁断。
        """
        pass
