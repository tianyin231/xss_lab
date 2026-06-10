from __future__ import annotations

import importlib
import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def settings_module() -> Any | None:
    try:
        return importlib.import_module("settings") # 加载本地配置
    except Exception:
        return None


def get(name: str, default: Any = None) -> Any:
    if name in os.environ:
        return os.environ[name] # 环境变量优先
    mod = settings_module() # 再读 settings.py
    if mod is not None and hasattr(mod, name):
        return getattr(mod, name)
    return default


def get_int(name: str, default: int) -> int:
    value = get(name, None)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except Exception:
        return default


def get_float(name: str, default: float) -> float:
    value = get(name, None)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def get_bool(name: str, default: bool) -> bool:
    value = get(name, None)
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default
