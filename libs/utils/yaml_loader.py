"""
YAML 配置文件加载工具。

统一加载 configs/ 目录下的 YAML 文件，并提供类型安全的访问。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 项目 configs 目录
_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


def load_yaml(filename: str, *, configs_dir: Path | None = None) -> dict[str, Any]:
    """
    加载指定 YAML 文件并返回字典。

    Args:
        filename: 文件名（不含路径），如 "risk_limits.yaml"
        configs_dir: 自定义配置目录，默认使用项目根下 configs/

    Returns:
        解析后的字典

    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: YAML 语法错误
    """
    base = configs_dir or _CONFIGS_DIR
    filepath = base / filename

    if not filepath.exists():
        raise FileNotFoundError(f"配置文件不存在: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"配置文件顶层必须是字典: {filepath}")

    logger.info("已加载配置文件: %s", filepath)
    return data


def load_markets_whitelist() -> dict[str, Any]:
    """加载市场白名单配置。"""
    return load_yaml("markets_whitelist.yaml")


def load_risk_limits() -> dict[str, Any]:
    """加载风控限制配置。"""
    return load_yaml("risk_limits.yaml")


def load_sizing_config() -> dict[str, Any]:
    """加载仓位管理配置。"""
    return load_yaml("sizing.yaml")


def load_sources_config() -> dict[str, Any]:
    """加载数据源配置。"""
    return load_yaml("sources.yaml")
