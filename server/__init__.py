"""
后端应用初始化模块
作用：配置 Flask 应用、注册路由、初始化数据库连接以及处理跨域等全局设置。
"""
from __future__ import annotations

import os
import importlib
from typing import Any

from flask import Flask
from flask import jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from server.api import api_bp
from server.db import db


def create_app() -> Flask:
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 处理数据库路径，确保它相对于项目根目录
    db_uri = _db_uri()
    if db_uri.startswith('sqlite:///'):
        # 提取相对路径部分
        db_path = db_uri.replace('sqlite:///', '')
        if not db_path.startswith('/'):
            # 构建绝对路径
            absolute_db_path = os.path.join(root_dir, db_path)
            db_uri = f'sqlite:///{absolute_db_path.replace(chr(92), "/")}'
    
    _ensure_database_if_needed(db_uri)

    app = Flask(__name__)
    # 根据数据库类型配置引擎选项
    engine_options = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }
    
    # 只对MySQL数据库应用连接池参数
    if db_uri.startswith(('mysql://', 'mysql+pymysql://')):
        engine_options.update({
            "pool_size": _get_int("MYSQL_POOL_SIZE", 10),
            "max_overflow": _get_int("MYSQL_MAX_OVERFLOW", 20),
        })
    
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=db_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options,
    )

    CORS(app, resources={r"/api/*": {"origins": _get("CORS_ORIGINS", "*")}})

    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/favicon.ico")
    def _favicon() -> Any:
        return "", 204

    @app.get("/")
    def _root() -> Any:
        return jsonify(
            {
                "name": str(_get("SYSTEM_NAME", "XSSLab")),
                "version": str(_get("SYSTEM_VERSION", "0.1.0")),
                "api_base": "/api",
                "health": "ok",
                "endpoints": [
                    "GET /api",
                    "POST /api/jobs",
                    "GET /api/jobs",
                    "GET /api/jobs/<job_id>",
                    "GET /api/jobs/<job_id>/report",
                    "GET /api/jobs/<job_id>/events",
                    "POST /api/jobs/<job_id>/stop",
                ],
            }
        )

    return app


def _settings_module() -> Any | None:
    try:
        return importlib.import_module("settings")
    except Exception:
        return None


_SETTINGS = _settings_module()


def _get(name: str, default: Any) -> Any:
    if name in os.environ:
        return os.environ[name]
    if _SETTINGS is not None and hasattr(_SETTINGS, name):
        return getattr(_SETTINGS, name)
    return default


def _get_int(name: str, default: int) -> int:
    v = _get(name, None)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def _db_uri() -> str:
    v = _get("DATABASE_URL", None)
    if v:
        return str(v)
    return _mysql_uri()


def _mysql_uri() -> str:
    user = str(_get("MYSQL_USER", "root"))
    password = str(_get("MYSQL_PASSWORD", ""))
    host = str(_get("MYSQL_HOST", "127.0.0.1"))
    port = str(_get("MYSQL_PORT", "3306"))
    database = str(_get("MYSQL_DATABASE", "server"))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def _ensure_database_if_needed(db_uri: str) -> None:
    try:
        url = make_url(db_uri)
    except Exception:
        return

    if (url.drivername or "").lower() not in {"mysql+pymysql", "mysql"}:
        return

    db_name = url.database
    if not db_name:
        return

    server_url = url.set(database=None)
    engine = create_engine(server_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4"))
    finally:
        engine.dispose()
