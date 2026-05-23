"""
Project settings loaded from config.yaml.

Environment variables are still used for secrets; this module keeps non-secret
defaults in one place so README/config.yaml and runtime behavior stay aligned.
"""
from __future__ import annotations

import copy
import os
from typing import Any

import yaml

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

DEFAULT_CONFIG: dict[str, Any] = {
    "reddit": {
        "default_subreddit": "all",
        "default_limit": 30,
        "search_sort": "relevance",
        "search_time_filter": "month",
    },
    "ai": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "filter_threshold": 5.0,
    },
    "database": {
        "path": "data/radar.db",
    },
    "webhook": {
        "max_posts_per_request": 25,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config() -> dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    if not os.path.exists(CONFIG_PATH):
        return config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    if isinstance(loaded, dict):
        _deep_merge(config, loaded)
    return config


def get_config_value(path: str, default: Any = None) -> Any:
    current: Any = load_config()
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def get_int_config(path: str, default: int) -> int:
    try:
        return int(get_config_value(path, default))
    except (TypeError, ValueError):
        return default


def get_float_config(path: str, default: float) -> float:
    try:
        return float(get_config_value(path, default))
    except (TypeError, ValueError):
        return default


def get_bool_config(path: str, default: bool) -> bool:
    value = get_config_value(path, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_project_path(path_value: str | None, default: str) -> str:
    raw_path = path_value or default
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.join(PROJECT_ROOT, raw_path)
