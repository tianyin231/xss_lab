"""
后端开发环境启动脚本
作用：以调试模式启动 Flask 后端服务器。
"""
from __future__ import annotations

import os

from app_config import get, get_bool, get_int
from server import create_app


def main() -> None:
    app = create_app()
    app.run(
        host=str(get("HOST", os.getenv("HOST", "127.0.0.1"))),
        port=get_int("PORT", int(os.getenv("PORT", "5001"))),
        debug=get_bool("FLASK_DEBUG", os.getenv("FLASK_DEBUG", "1") == "1"),
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
