"""
系统级全局日志控制。
支持控制台彩色输出与生产 Metrics 审计日志规范。
"""
import logging
import sys
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from libs.models.settings import get_settings

def setup_logging() -> None:
    settings = get_settings()
    level = logging.DEBUG if settings.app_env == "development" else logging.INFO
    
    # 清除旧的 handlers 防止重复打印
    logging.root.handlers = []
    
    if settings.app_env == "production":
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                # 生产输出：带有标准标签的 JSON
                log_record = {
                    "timestamp": datetime.fromtimestamp(record.created, tz=ZoneInfo("UTC")).isoformat(),
                    "level": record.levelname,
                    "service": "polymarket-agent",
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                     log_record["exc_info"] = self.formatException(record.exc_info)
                return json.dumps(log_record)
                
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logging.root.addHandler(handler)
        logging.root.setLevel(level)
    else:
        # 开发输出：直观文本
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.StreamHandler(sys.stdout)]
        )

    logging.info("[Logger] Globally initialized in %s mode.", settings.app_env)
