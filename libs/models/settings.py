"""
全局应用配置，使用 pydantic-settings 从环境变量加载。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用级别配置，自动从 .env / 环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 数据库 ----------
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/polymarket_agent"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/polymarket_agent"

    # ---------- Redis ----------
    redis_url: str = "redis://localhost:6379/0"

    # ---------- 6551 OpenNews ----------
    opennews_token: str = ""
    opennews_base_url: str = "https://api.opennews.6551.io/v1"
    opennews_ws_url: str = "wss://ws.opennews.6551.io/v1/stream"

    # ---------- Polymarket ----------
    polymarket_private_key: str = ""
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_passphrase: str = ""

    # ---------- Hermes ----------
    hermes_endpoint: str = ""
    hermes_api_key: str = ""

    # ---------- 应用 ----------
    app_env: str = "development"
    dry_run: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """单例获取全局配置。"""
    return Settings()
