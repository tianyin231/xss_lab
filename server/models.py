"""数据库模型定义。"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from server.db import db


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    stopped = "stopped"
    failed = "failed"
    finished = "finished"


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        Index("ix_users_username", "username"),
        Index("ix_users_auth_token", "auth_token"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(128), nullable=True)
    auth_token = db.Column(db.String(128), nullable=True)
    auth_token_created_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Job(db.Model):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )

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
    __table_args__ = (
        Index("ix_pages_job_id_id", "job_id", "id"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    url = db.Column(db.Text, nullable=False)
    status_code = db.Column(db.Integer, nullable=True)
    content_type = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Finding(db.Model):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_job_id_url", "job_id", "url"),
        Index("ix_findings_job_id_kind", "job_id", "kind"),
    )

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
    __table_args__ = (
        Index("ix_logs_job_id_id", "job_id", "id"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AIReport(db.Model):
    __tablename__ = "ai_reports"
    __table_args__ = (
        Index("ix_ai_reports_job_id_page_id", "job_id", "page_id"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    page_id = db.Column(db.Integer, index=True, nullable=False)
    page_url = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    accuracy = db.Column(db.Text, nullable=True)
    false_positives = db.Column(db.Text, nullable=True)
    false_negatives = db.Column(db.Text, nullable=True)
    suggestions = db.Column(db.Text, nullable=True)
    risk_assessment = db.Column(db.Text, nullable=True)
    full_report = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class DynamicVerification(db.Model):
    __tablename__ = "dynamic_verifications"
    __table_args__ = (
        Index("ix_dynamic_verifications_job_id_page_url", "job_id", "page_url"),
        Index("ix_dynamic_verifications_job_id_vector", "job_id", "vector"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    page_id = db.Column(db.Integer, index=True, nullable=True)
    page_url = db.Column(db.Text, nullable=False)
    target_url = db.Column(db.Text, nullable=False)
    vector = db.Column(db.String(32), nullable=False)
    parameter_name = db.Column(db.String(128), nullable=True)
    payload = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False)
    evidence = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AIPayloadReport(db.Model):
    __tablename__ = "ai_payload_reports"
    __table_args__ = (
        Index("ix_ai_payload_reports_job_id_page_url", "job_id", "page_url"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    page_url = db.Column(db.Text, nullable=False)
    finding_kind = db.Column(db.String(64), nullable=True)
    finding_title = db.Column(db.String(255), nullable=True)
    mode = db.Column(db.String(16), nullable=False, default="exploit")
    payloads_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class FindingStatus(db.Model):
    __tablename__ = "finding_statuses"
    __table_args__ = (
        UniqueConstraint("job_id", "finding_kind", "finding_title", name="uq_finding_status_job_kind_title"),
        Index("ix_finding_statuses_job_id_kind_title", "job_id", "finding_kind", "finding_title"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(36), index=True, nullable=False)
    finding_kind = db.Column(db.String(64), nullable=False)
    finding_title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="open")
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
