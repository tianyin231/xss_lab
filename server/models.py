"""
数据库模型模块
作用：定义数据库表结构，包括任务 (Job)、页面 (Page)、发现记录 (Finding) 和日志 (Log)。
"""
from __future__ import annotations

import enum
from datetime import datetime

from server.db import db


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    stopped = "stopped"
    failed = "failed"
    finished = "finished"


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String(36), primary_key=True)
    target_url = db.Column(db.Text, nullable=False)
    max_depth = db.Column(db.Integer, nullable=False)
    max_pages = db.Column(db.Integer, nullable=False)
    use_selenium = db.Column(db.Boolean, nullable=False, default=False)

    status = db.Column(db.String(32), nullable=False, default=JobStatus.queued.value)
    error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)


class Page(db.Model):
    __tablename__ = "pages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    url = db.Column(db.Text, nullable=False)
    status_code = db.Column(db.Integer, nullable=True)
    content_type = db.Column(db.String(255), nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Finding(db.Model):
    __tablename__ = "findings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    url = db.Column(db.Text, nullable=False)
    kind = db.Column(db.String(64), nullable=False)
    severity = db.Column(db.String(16), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    evidence = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Log(db.Model):
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AIReport(db.Model):
    __tablename__ = "ai_reports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    page_url = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    accuracy = db.Column(db.Text, nullable=True)
    false_positives = db.Column(db.Text, nullable=True)  # JSON格式存储
    false_negatives = db.Column(db.Text, nullable=True)  # JSON格式存储
    suggestions = db.Column(db.Text, nullable=True)  # JSON格式存储
    risk_assessment = db.Column(db.Text, nullable=True)
    full_report = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
