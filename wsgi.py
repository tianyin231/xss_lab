"""
WSGI 入口文件
作用：用于生产环境部署（如 Gunicorn/uWSGI）的应用程序实例。
"""
from __future__ import annotations

from server import create_app

app = create_app()
