"""
后端应用初始化模块
作用：配置 Flask 应用、注册路由、初始化数据库连接以及处理跨域等全局设置。
"""
from __future__ import annotations

import os

from app_config import get, get_int
from flask import Flask, Response, jsonify
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
    
    _ensure_database_if_needed(db_uri) # MySQL 不存在时自动建库

    app = Flask(__name__)
    # 根据数据库类型配置引擎选项
    engine_options = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }
    
    # 只对MySQL数据库应用连接池参数
    if db_uri.startswith(('mysql://', 'mysql+pymysql://')):
        engine_options.update({
            "pool_size": get_int("MYSQL_POOL_SIZE", 10),
            "max_overflow": get_int("MYSQL_MAX_OVERFLOW", 20),
        })
    
    app.config.from_mapping( # 注入 Flask/SQLAlchemy 配置
        SQLALCHEMY_DATABASE_URI=db_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options,
    )

    CORS(app, resources={r"/api/*": {"origins": get("CORS_ORIGINS", "*")}}) # 允许前端访问 API

    db.init_app(app) # 绑定 ORM
    with app.app_context():
        db.create_all() # 创建数据表

    app.register_blueprint(api_bp, url_prefix="/api") # 注册 API 路由

    @app.get("/favicon.ico")
    def _favicon() -> Response:
        return "", 204

    @app.get("/")
    def _root() -> Response:
        return jsonify(
            {
                "name": str(get("SYSTEM_NAME", "XSS漏洞自动化挖掘工具")),
                "version": str(get("SYSTEM_VERSION", "0.1.0")),
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
def _db_uri() -> str:
    v = get("DATABASE_URL", None) # 优先读取显式数据库配置
    if v:
        return str(v)
    return _mysql_uri()


def _mysql_uri() -> str:
    user = str(get("MYSQL_USER", "root"))
    password = str(get("MYSQL_PASSWORD", ""))
    host = str(get("MYSQL_HOST", "127.0.0.1"))
    port = str(get("MYSQL_PORT", "3306"))
    database = str(get("MYSQL_DATABASE", "server"))
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def _ensure_database_if_needed(db_uri: str) -> None:
    try:
        url = make_url(db_uri) # 解析数据库连接串
    except Exception:
        return

    if (url.drivername or "").lower() not in {"mysql+pymysql", "mysql"}:
        return

    db_name = url.database
    if not db_name:
        return

    server_url = url.set(database=None)
    engine = create_engine(server_url) # 连接 MySQL 服务端
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")) # 确保库存在
    finally:
        engine.dispose()
