"""
后端开发环境启动脚本
作用：以调试模式启动 Flask 后端服务器。
"""
from __future__ import annotations

import os
import importlib
from typing import Any

from server import create_app


def main() -> None:
    app = create_app()
    cfg = _settings_module()
    app.run(
        host=_get(cfg, "HOST", os.getenv("HOST", "127.0.0.1")),
        port=int(_get(cfg, "PORT", os.getenv("PORT", "5000"))),
        debug=_get_bool(cfg, "FLASK_DEBUG", os.getenv("FLASK_DEBUG", "1") == "1"),
        threaded=True,
        use_reloader=False,
    )


def _settings_module() -> Any | None:
    try:
        return importlib.import_module("settings")
    except Exception:
        return None


def _get(mod: Any | None, name: str, default: Any) -> Any:
    if name in os.environ:
        return os.environ[name]
    if mod is not None and hasattr(mod, name):
        return getattr(mod, name)
    return default


def _get_bool(mod: Any | None, name: str, default: bool) -> bool:
    v = _get(mod, name, None)
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default


if __name__ == "__main__":
    main()
