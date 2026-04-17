"""
结构化日志配置。

使用 structlog 提供 JSON 格式日志，便于生产环境日志采集。
"""

from __future__ import annotations

import logging
import sys

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover - fallback for lean test envs
    structlog = None

from libs.models.settings import get_settings


def setup_logging() -> None:
    """初始化全局日志配置。应在应用启动时调用一次。"""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 标准库日志基础配置
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    if structlog is None:
        logging.getLogger(__name__).warning(
            "structlog is not installed; falling back to stdlib logging only."
        )
        return

    # structlog 处理器链
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.app_env == "development":
        # 开发环境使用彩色可读输出
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # 生产环境输出 JSON
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
