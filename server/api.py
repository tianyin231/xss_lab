"""HTTP API 路由。"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

if __package__ in {None, ""}:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

from ai import get_analyzer
from app_config import get, get_bool, get_int
from flask import Blueprint, Response, g, jsonify, request
from lxml import html as lxml_html
from sqlalchemy import func

from server.db import db
from server.auth import extract_bearer_token, hash_password, issue_token, serialize_user, verify_password
from server.dynamic_verify import (
    build_safe_probe_candidates_for_page,
    retest_finding,
    retest_page,
    run_ai_multi_round_validation,
    suggest_payloads_for_finding,
    suggest_payloads_for_page,
)
from server.models import AIReport, AIPayloadReport, DynamicVerification, Finding, FindingStatus, Job, Log, Page, User
from server.report_export import build_export_filename, render_report_html, render_report_json
from server.runner import bus, runner

api_bp = Blueprint("api", __name__)
BEIJING_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc
PUBLIC_API_PATHS = {
    "/api",
    "/api/",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/me",
}


@api_bp.before_app_request
def require_api_auth() -> Response | None:
    path = request.path or ""
    if request.method == "OPTIONS":
        return None
    if not path.startswith("/api"):
        return None
    if path in PUBLIC_API_PATHS:
        return None

    token = extract_bearer_token(request.headers.get("Authorization")) or str(request.args.get("auth_token") or "").strip()
    if not token:
        return jsonify({"error": "auth required"}), 401

    user = User.query.filter_by(auth_token=token).first() # 校验登录状态
    if user is None:
        return jsonify({"error": "invalid token"}), 401

    g.current_user = user
    return None


@api_bp.get("")
@api_bp.get("/")
def api_root() -> Response:
    return jsonify({"api": "ok"})


@api_bp.post("/auth/register")
def register() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    display_name = str(payload.get("display_name") or "").strip() or None
    invite_code = str(payload.get("invite_code") or "").strip()
    expected_invite_code = str(get("AUTH_INVITE_CODE", "xsslab-2026")).strip()

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if len(username) < 3:
        return jsonify({"error": "username too short"}), 400
    if len(password) < 6:
        return jsonify({"error": "password too short"}), 400
    if invite_code != expected_invite_code:
        return jsonify({"error": "invalid invite code"}), 400
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"error": "username already exists"}), 400

    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    token = issue_token(user)
    user.auth_token_created_at = datetime.utcnow()
    db.session.add(user)
    db.session.commit()
    return jsonify({"ok": True, "user": serialize_user(user), "token": token}), 201


@api_bp.post("/auth/login")
def login() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if user is None or not verify_password(user.password_hash, password):
        return jsonify({"error": "invalid username or password"}), 401

    token = issue_token(user)
    user.auth_token_created_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "user": serialize_user(user), "token": token})


@api_bp.get("/auth/me")
def auth_me() -> Response:
    token = extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return jsonify({"authenticated": False, "user": None}), 200
    user = User.query.filter_by(auth_token=token).first()
    if user is None:
        return jsonify({"authenticated": False, "user": None}), 200
    return jsonify({"authenticated": True, "user": serialize_user(user)})


@api_bp.post("/auth/logout")
def logout() -> Response:
    user: User | None = getattr(g, "current_user", None)
    if user is None:
        return jsonify({"ok": True})
    user.auth_token = None
    user.auth_token_created_at = None
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.get("/workbench/url")
def get_workbench_url() -> Response:
    job_id = str(request.args.get("job_id") or "").strip()
    page_url = str(request.args.get("page_url") or "").strip()
    params: dict[str, str] = {}
    if job_id:
        params["job_id"] = job_id
    if page_url:
        params["page_url"] = page_url
    current_user: User | None = getattr(g, "current_user", None)
    if current_user and current_user.auth_token:
        params["auth_token"] = current_user.auth_token
    query = urlencode(params)
    url = "/workbench.html"
    if query:
        url = f"{url}?{query}"
    return jsonify({"ok": True, "url": url})


@api_bp.post("/jobs")
def create_job() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    target_url = str(payload.get("target_url") or "").strip()
    max_depth = int(payload.get("max_depth") or get_int("MAX_DEPTH_DEFAULT", 2))
    max_pages = int(payload.get("max_pages") or get_int("MAX_PAGES_DEFAULT", 200))
    use_selenium = bool(payload.get("use_selenium") or get_bool("USE_SELENIUM_DEFAULT", False))

    if not target_url:
        return jsonify({"error": "target_url required"}), 400

    job_id = runner.create_job(
        target_url=target_url,
        max_depth=max_depth,
        max_pages=max_pages,
        use_selenium=use_selenium,
    )  # 创建任务
    runner.start_job(job_id)  # 启动后台扫描
    return jsonify({"job_id": job_id}), 201


@api_bp.get("/jobs")
def list_jobs() -> Response:
    jobs = Job.query.order_by(Job.created_at.desc()).limit(200).all()
    return jsonify(
        [
            {
                "id": j.id,
                "target_url": j.target_url,
                "max_depth": j.max_depth,
                "max_pages": j.max_pages,
                "use_selenium": bool(j.use_selenium),
                "status": j.status,
                "error": j.error,
                "created_at": _to_beijing_iso(j.created_at),
                "started_at": _to_beijing_iso(j.started_at),
                "finished_at": _to_beijing_iso(j.finished_at),
            }
            for j in jobs
        ]
    )


@api_bp.get("/jobs/<job_id>")
def get_job(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        {
            "id": job.id,
            "target_url": job.target_url,
            "max_depth": job.max_depth,
            "max_pages": job.max_pages,
            "use_selenium": bool(job.use_selenium),
            "status": job.status,
            "error": job.error,
            "created_at": _to_beijing_iso(job.created_at),
            "started_at": _to_beijing_iso(job.started_at),
            "finished_at": _to_beijing_iso(job.finished_at),
        }
    )


@api_bp.post("/jobs/<job_id>/stop")
def stop_job(job_id: str) -> Response:
    runner.stop_job(job_id)
    return jsonify({"ok": True})


@api_bp.delete("/jobs/<job_id>")
def delete_job(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    runner.stop_job(job_id)
    Page.query.filter_by(job_id=job_id).delete()
    Finding.query.filter_by(job_id=job_id).delete()
    Log.query.filter_by(job_id=job_id).delete()
    AIReport.query.filter_by(job_id=job_id).delete()
    DynamicVerification.query.filter_by(job_id=job_id).delete()
    FindingStatus.query.filter_by(job_id=job_id).delete()
    db.session.delete(job)
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.post("/jobs/<job_id>/finding-status")
def update_finding_status(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    finding_kind = str(payload.get("kind") or "").strip()
    finding_title = str(payload.get("title") or "").strip()
    status = str(payload.get("status") or "open").strip().lower()
    note = str(payload.get("note") or "").strip() or None
    allowed_statuses = {"open", "confirmed", "false_positive", "fixed", "ignored"}

    if not finding_kind or not finding_title:
        return jsonify({"error": "kind and title required"}), 400
    if status not in allowed_statuses:
        return jsonify({"error": "invalid status"}), 400

    record = FindingStatus.query.filter_by(
        job_id=job_id,
        finding_kind=finding_kind,
        finding_title=finding_title,
    ).first()
    if record is None:
        record = FindingStatus(
            job_id=job_id,
            finding_kind=finding_kind,
            finding_title=finding_title,
            status=status,
            note=note,
        )
        db.session.add(record)
    else:
        record.status = status
        record.note = note

    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "status": record.status,
            "note": record.note,
            "updated_at": _to_beijing_iso(record.updated_at),
        }
    )


@api_bp.get("/jobs/<job_id>/report")
def get_report(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_build_report_payload(job)) # 聚合扫描报告


@api_bp.get("/jobs/<job_id>/pages")
def list_job_pages(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    pages = Page.query.filter_by(job_id=job_id).order_by(Page.id.desc()).all() # 查询任务页面
    return jsonify(
        {
            "ok": True,
            "pages": [
                {
                    "id": item.id,
                    "url": item.url,
                    "status_code": item.status_code,
                    "content_type": item.content_type,
                    "fetched_at": _to_beijing_iso(item.fetched_at),
                }
                for item in pages
            ],
        }
    )


@api_bp.get("/jobs/<job_id>/export")
def export_report(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    export_format = str(request.args.get("format") or "html").strip().lower()
    if export_format not in {"html", "json"}:
        return jsonify({"error": "unsupported format"}), 400

    report_payload = _build_report_payload(job, include_export_details=True) # 导出完整报告
    if export_format == "json":
        body = render_report_json(report_payload) # 生成 JSON 报告
        mimetype = "application/json; charset=utf-8"
    else:
        body = render_report_html(report_payload) # 生成 HTML 报告
        mimetype = "text/html; charset=utf-8"

    return Response(
        body,
        mimetype=mimetype,
        headers={
            "Content-Disposition": f'attachment; filename="{build_export_filename(job.id, export_format)}"' # 下载文件名
        },
    )


@api_bp.get("/jobs/<job_id>/events")
def job_events(job_id: str) -> Response:
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(bus.stream(job_id), headers=headers)  # SSE 实时推送


@api_bp.post("/jobs/<job_id>/analyze")
def analyze_job(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    pages = Page.query.filter_by(job_id=job_id).all()
    findings = Finding.query.filter_by(job_id=job_id).all()
    if not pages:
        db.session.add(Log(job_id=job_id, message="[AI分析] 分析失败：没有找到可分析页面"))
        db.session.commit()
        return jsonify({"error": "no pages found"}), 400

    db.session.add(Log(job_id=job_id, message=f"[AI分析] 开始分析任务，共 {len(pages)} 个页面"))
    reports = []
    analyzer = get_analyzer()

    for page in pages:
        page_findings = [f for f in findings if f.url == page.url]
        page_verifications = (
            DynamicVerification.query.filter_by(job_id=job_id, page_url=page.url)
            .order_by(DynamicVerification.id.desc())
            .limit(30)
            .all()
        )
        input_profile = _build_page_input_profile(page)
        serialized_verifications = [_serialize_verification(item) for item in page_verifications]
        successful_payloads = _build_successful_payloads(serialized_verifications)
        test_result = {
            "url": page.url,
            "status_code": page.status_code,
            "content_type": page.content_type,
            "input_profile": input_profile,
            "risk_summary": _build_page_risk_summary(page_findings, page_verifications, input_profile),
            "findings": [
                {
                    "kind": f.kind,
                    "severity": f.severity,
                    "title": f.title,
                    "evidence": f.evidence,
                }
                for f in page_findings
            ],
            "dynamic_verifications": serialized_verifications[:12],
            "successful_payloads": successful_payloads[:8],
            "payload_suggestions": suggest_payloads_for_page(page, page_findings)[:8],
            "analysis_guidance": {
                "assessment_policy": "请综合静态发现、动态验证和页面输入面判断。静态低危线索不等于误报；它可能是用于后续动态验证的风险信号。若存在 verified 动态验证或 successful_payloads，应优先认为系统已获得较高置信度证据。",
                "false_positive_policy": "只有在明确证明该 finding 与用户可控输入无关、不可达、或被上下文安全编码处理时，才应判为误报。不要仅因为 finding 类型是 tainted_source、javascript_redirection 或 dom_sink 就直接判为误报。",
                "accuracy_policy": "评价系统准确率时，应说明系统采用了静态分析、AST 污点分析和动态验证的组合方法；若动态验证结果支持风险，应肯定这种多阶段验证提高了准确性。",
            },
        }

        db.session.add(Log(job_id=job_id, message=f"[AI分析] 开始分析页面：{page.url}"))
        try:
            analysis = analyzer.analyze_xss_result(page.content or "", test_result)
            if not analysis.get("success"):
                raise RuntimeError(str(analysis.get("error") or "AI analysis failed"))

            result = analysis["analysis"]
            ai_report = AIReport(
                job_id=job_id,
                page_id=page.id,
                page_url=page.url,
                summary=result["summary"],
                accuracy=result.get("accuracy"),
                false_positives=json.dumps(result.get("false_positives") or [], ensure_ascii=False),
                false_negatives=json.dumps(result.get("false_negatives") or [], ensure_ascii=False),
                suggestions=json.dumps(result.get("suggestions") or [], ensure_ascii=False),
                risk_assessment=result.get("risk_assessment"),
                full_report=result["full_report"],
            )
            db.session.add(ai_report)
            db.session.add(Log(job_id=job_id, message=f"[AI分析] 页面分析成功：{page.url}"))
            reports.append(analysis)
        except Exception as e:
            db.session.add(Log(job_id=job_id, message=f"[AI分析] 页面分析失败：{page.url} - {str(e)}"))
            fallback_analysis = {
                "success": True,
                "analysis": {
                    "summary": f"AI analysis failed for {page.url}",
                    "accuracy": "unknown",
                    "false_positives": ["当前未生成模型报告，无法判断误报情况"],
                    "false_negatives": ["当前未生成模型报告，无法判断是否遗漏 XSS 风险"],
                    "suggestions": [
                        "检查 AI_API_KEY 和 AI_BASE_URL 配置",
                        "确认网络与 TLS 连接是否正常",
                        "修复上游 AI 服务错误后重新分析",
                    ],
                    "risk_assessment": "AI 服务不可用，本次未生成可靠的风险评估。",
                    "full_report": (
                        f"AI analysis failed for page: {page.url}\n\n"
                        f"Error: {e}\n\n"
                        "No model-generated report was available, so this fallback record was saved."
                    ),
                },
            }

            fallback_report = AIReport(
                job_id=job_id,
                page_id=page.id,
                page_url=page.url,
                summary=fallback_analysis["analysis"]["summary"],
                accuracy=fallback_analysis["analysis"]["accuracy"],
                false_positives=json.dumps(fallback_analysis["analysis"]["false_positives"], ensure_ascii=False),
                false_negatives=json.dumps(fallback_analysis["analysis"]["false_negatives"], ensure_ascii=False),
                suggestions=json.dumps(fallback_analysis["analysis"]["suggestions"], ensure_ascii=False),
                risk_assessment=fallback_analysis["analysis"]["risk_assessment"],
                full_report=fallback_analysis["analysis"]["full_report"],
            )
            db.session.add(fallback_report)
            reports.append(fallback_analysis)

    db.session.add(Log(job_id=job_id, message=f"[AI分析] 分析完成，生成 {len(reports)} 份报告"))
    db.session.commit()
    return jsonify({"success": True, "reports": reports})


@api_bp.post("/jobs/<job_id>/findings/retest")
def retest_job_finding(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    finding_kind = str(payload.get("kind") or "").strip()
    finding_title = str(payload.get("title") or "").strip()
    finding_url = str(payload.get("url") or "").strip()
    finding_evidence = str(payload.get("evidence") or "").strip()
    finding_severity = str(payload.get("severity") or "").strip() or "medium"
    member_kinds = payload.get("member_kinds") or []
    urls = payload.get("urls") or []
    custom_payload = str(payload.get("payload") or "").strip() or None
    vector = str(payload.get("vector") or "").strip() or None
    use_selenium_raw = payload.get("use_selenium")
    use_selenium = use_selenium_raw if isinstance(use_selenium_raw, bool) else None

    if not finding_kind or not finding_title:
        return jsonify({"error": "kind and title required"}), 400

    finding = _locate_finding(
        job_id=job_id,
        finding_kind=finding_kind,
        finding_title=finding_title,
        finding_url=finding_url,
        member_kinds=member_kinds if isinstance(member_kinds, list) else [],
        urls=urls if isinstance(urls, list) else [],
    ) # 定位要复测的风险点
    if finding is None and finding_url:
        finding = _build_virtual_finding(
            job_id=job_id,
            finding_url=finding_url,
            finding_kind=finding_kind,
            finding_title=finding_title,
            finding_evidence=finding_evidence,
            finding_severity=finding_severity,
        ) # 构造临时风险点
    if finding is None:
        return jsonify({"error": "finding not found"}), 404

    try:
        records = retest_finding(
            job_id=job_id,
            finding=finding,
            payload=custom_payload,
            vector=vector,
            use_selenium=use_selenium,
        ) # 单个风险点复测
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        db.session.add(Log(job_id=job_id, message=f"[单点复测] {finding.title} - {exc}"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 500

    db.session.add(
        Log(
            job_id=job_id,
            message=f"[单点复测] {finding.title} -> {len(records)} 条结果",
        )
    )
    _persist_runtime_verifications(job_id, records) # 保存复测结果
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "finding": {
                "kind": finding.kind,
                "title": finding.title,
                "url": finding.url,
            },
            "results": [_serialize_runtime_verification(item) for item in records],
        }
    )


@api_bp.post("/jobs/<job_id>/findings/payloads")
def suggest_job_finding_payloads(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    finding_kind = str(payload.get("kind") or "").strip()
    finding_title = str(payload.get("title") or "").strip()
    finding_url = str(payload.get("url") or "").strip()
    finding_evidence = str(payload.get("evidence") or "").strip()
    finding_severity = str(payload.get("severity") or "").strip() or "medium"
    member_kinds = payload.get("member_kinds") or []
    urls = payload.get("urls") or []
    if not finding_kind or not finding_title:
        return jsonify({"error": "kind and title required"}), 400

    finding = _locate_finding(
        job_id=job_id,
        finding_kind=finding_kind,
        finding_title=finding_title,
        finding_url=finding_url,
        member_kinds=member_kinds if isinstance(member_kinds, list) else [],
        urls=urls if isinstance(urls, list) else [],
    )
    if finding is None and finding_url:
        finding = _build_virtual_finding(
            job_id=job_id,
            finding_url=finding_url,
            finding_kind=finding_kind,
            finding_title=finding_title,
            finding_evidence=finding_evidence,
            finding_severity=finding_severity,
        )
    if finding is None:
        return jsonify({"error": "finding not found"}), 404

    return jsonify(
        {
            "ok": True,
            "finding": {
                "kind": finding.kind,
                "title": finding.title,
                "url": finding.url,
            },
            "payloads": suggest_payloads_for_finding(finding),
        }
    )


@api_bp.post("/jobs/<job_id>/pages/retest")
def retest_job_page(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    page_url = str(payload.get("url") or "").strip()
    custom_payload = str(payload.get("payload") or "").strip() or None
    vector = str(payload.get("vector") or "").strip() or None
    use_selenium_raw = payload.get("use_selenium")
    use_selenium = use_selenium_raw if isinstance(use_selenium_raw, bool) else None
    if not page_url:
        return jsonify({"error": "url required"}), 400

    page = Page.query.filter_by(job_id=job_id, url=page_url).order_by(Page.id.desc()).first()
    if page is None:
        return jsonify({"error": "page not found"}), 404

    batch_id = uuid4().hex
    strategy = _build_page_retest_strategy(page, Finding.query.filter_by(job_id=job_id, url=page.url).all(), _build_page_input_profile(page)) # 生成页面复测策略
    try:
        records = retest_page(
            job_id=job_id,
            page=page,
            payload=custom_payload,
            vector=vector,
            use_selenium=use_selenium,
        ) # 页面级复测
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        db.session.add(Log(job_id=job_id, message=f"[页面复测] {page.url} - {exc}"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 500

    db.session.add(Log(job_id=job_id, message=f"[页面复测] {page.url} -> {len(records)} 条结果"))
    _persist_runtime_verifications(
        job_id,
        records,
        batch_id=batch_id,
        report_meta={
            "reason": strategy.get("reason"),
            "preferred_vector": strategy.get("preferred_vector"),
            "preferred_payload": strategy.get("preferred_payload", {}).get("payload")
            if isinstance(strategy.get("preferred_payload"), dict)
            else None,
        },
    ) # 保存页面复测结果
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "batch_id": batch_id,
            "page": {
                "id": page.id,
                "url": page.url,
            },
            "results": [_serialize_runtime_verification(item) for item in records],
        }
    )


@api_bp.delete("/jobs/<job_id>/pages/retest-reports/<batch_id>")
def delete_page_retest_report(job_id: str, batch_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    page_url = str(request.args.get("url") or "").strip()
    if not page_url:
        return jsonify({"error": "url required"}), 400

    records = (
        DynamicVerification.query.filter_by(job_id=job_id, page_url=page_url)
        .order_by(DynamicVerification.id.asc())
        .all()
    )
    matched: list[DynamicVerification] = []
    for item in records:
        detail = _parse_dynamic_evidence(item.evidence)
        if detail.get("source") != "manual_retest":
            continue
        detail_batch_id = detail.get("batch_id")
        legacy_batch_id = f"legacy-{item.id}"
        if batch_id == detail_batch_id or (detail_batch_id is None and batch_id == legacy_batch_id):
            matched.append(item)

    if not matched:
        return jsonify({"error": "report not found"}), 404

    for item in matched:
        db.session.delete(item)
    db.session.add(Log(job_id=job_id, message=f"[页面复测] 删除复测报告 {batch_id}，共 {len(matched)} 条记录"))
    db.session.commit()
    return jsonify({"ok": True, "deleted": len(matched), "batch_id": batch_id})


@api_bp.delete("/jobs/<job_id>/pages/retest-results/<int:verification_id>")
def delete_page_retest_result(job_id: str, verification_id: int) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    item: DynamicVerification | None = db.session.get(DynamicVerification, verification_id)
    if item is None or item.job_id != job_id:
        return jsonify({"error": "result not found"}), 404

    detail = _parse_dynamic_evidence(item.evidence)
    if detail.get("source") != "manual_retest":
        return jsonify({"error": "only manual retest result can be deleted"}), 400

    page_url = str(request.args.get("url") or "").strip()
    if page_url and item.page_url != page_url:
        return jsonify({"error": "result not found"}), 404

    db.session.delete(item)
    db.session.add(Log(job_id=job_id, message=f"[页面复测] 删除复测结果 {verification_id}"))
    db.session.commit()
    return jsonify({"ok": True, "deleted": 1, "id": verification_id})


@api_bp.post("/jobs/<job_id>/pages/payloads")
def suggest_job_page_payloads(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    page_url = str(payload.get("url") or "").strip()
    if not page_url:
        return jsonify({"error": "url required"}), 400

    page = Page.query.filter_by(job_id=job_id, url=page_url).order_by(Page.id.desc()).first()
    if page is None:
        return jsonify({"error": "page not found"}), 404

    findings = Finding.query.filter_by(job_id=job_id, url=page.url).all()
    return jsonify(
        {
            "ok": True,
            "page": {
                "id": page.id,
                "url": page.url,
            },
            "payloads": suggest_payloads_for_page(page, findings),
        }
    )


@api_bp.get("/jobs/<job_id>/pages/workbench")
def get_page_workbench(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    page_url = str(request.args.get("url") or "").strip()
    if not page_url:
        return jsonify({"error": "url required"}), 400

    page = Page.query.filter_by(job_id=job_id, url=page_url).order_by(Page.id.desc()).first()
    if page is None:
        return jsonify({"error": "page not found"}), 404

    findings = Finding.query.filter_by(job_id=job_id, url=page.url).order_by(Finding.id.asc()).all()
    verifications = (
        DynamicVerification.query.filter_by(job_id=job_id, page_url=page.url)
        .order_by(DynamicVerification.id.desc())
        .all()
    )
    manual_retests = [item for item in verifications if _parse_dynamic_evidence(item.evidence).get("source") == "manual_retest"]
    ai_multi_round_retests = [item for item in verifications if _parse_dynamic_evidence(item.evidence).get("source") == "ai_multi_round"]
    dynamic_results = [
        item
        for item in verifications
        if _parse_dynamic_evidence(item.evidence).get("source") not in {"manual_retest", "ai_multi_round"}
    ]
    manual_retest_reports = _build_manual_retest_reports(manual_retests)
    ai_multi_round_reports = _build_runtime_reports(ai_multi_round_retests, source="ai_multi_round")
    serialized_page_verifications = [_serialize_verification(item) for item in verifications]
    serialized_manual_retests: list[dict[str, object]] = []
    serialized_dynamic_results: list[dict[str, object]] = []

    for item in serialized_page_verifications:
        if item.get("source") == "manual_retest" and len(serialized_manual_retests) < 20:
            serialized_manual_retests.append(item)
        elif item.get("source") not in {"manual_retest", "ai_multi_round"} and len(serialized_dynamic_results) < 20:
            serialized_dynamic_results.append(item)

    input_profile = _build_page_input_profile(page) # 提取页面输入面
    return jsonify(
        {
            "ok": True,
            "page": {
                "id": page.id,
                "job_id": page.job_id,
                "url": page.url,
                "status_code": page.status_code,
                "content_type": page.content_type,
                "sha256": page.sha256,
                "content": page.content,
                "fetched_at": _to_beijing_iso(page.fetched_at),
            },
            "input_profile": input_profile,
            "risk_summary": _build_page_risk_summary(findings, verifications, input_profile),
            "repair_suggestions": _build_page_repair_suggestions(findings, input_profile),
            "related_findings": _serialize_workbench_findings(findings),
            "manual_retests": serialized_manual_retests,
            "latest_manual_retest_report": manual_retest_reports[0] if manual_retest_reports else None,
            "manual_retest_reports": manual_retest_reports[:20],
            "latest_ai_multi_round_report": ai_multi_round_reports[0] if ai_multi_round_reports else None,
            "ai_multi_round_reports": ai_multi_round_reports[:10],
            "ai_payload_reports": _serialize_ai_payload_reports(job_id, page.url),
            "dynamic_results": serialized_dynamic_results,
            "successful_payloads": _build_successful_payloads(serialized_page_verifications),
            "payloads": suggest_payloads_for_page(page, findings),
            "retest_strategy": _build_page_retest_strategy(page, findings, input_profile),
        }
    )


@api_bp.post("/jobs/<job_id>/pages/ai-validate")
def ai_validate_page_workbench(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    page_url = str(payload.get("url") or "").strip()
    mode = str(payload.get("mode") or "standard").strip().lower()
    use_selenium_raw = payload.get("use_selenium")
    use_selenium = use_selenium_raw if isinstance(use_selenium_raw, bool) else None
    if mode not in {"quick", "standard", "deep"}:
        return jsonify({"error": "invalid mode"}), 400
    if not page_url:
        return jsonify({"error": "url required"}), 400

    page = Page.query.filter_by(job_id=job_id, url=page_url).order_by(Page.id.desc()).first()
    if page is None:
        return jsonify({"error": "page not found"}), 404

    findings = Finding.query.filter_by(job_id=job_id, url=page.url).order_by(Finding.id.asc()).all()
    input_profile = _build_page_input_profile(page)
    page_context = {
        "url": page.url,
        "status_code": page.status_code,
        "content_type": page.content_type,
        "input_profile": input_profile,
        "risk_summary": _build_page_risk_summary(findings, [], input_profile),
        "related_findings": _serialize_workbench_findings(findings)[:6],
    }
    candidates = build_safe_probe_candidates_for_page(page, findings, mode) # 生成安全探针候选
    ai_plan = _recommend_ai_multi_round_plan(page_context, candidates, mode) # AI 选择验证轮次
    batch_id = uuid4().hex

    try:
        round_outputs = run_ai_multi_round_validation(job_id, page, ai_plan["rounds"], use_selenium=use_selenium) # 执行多轮验证
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        db.session.add(Log(job_id=job_id, message=f"[AI多轮验证] {page.url} - {exc}"))
        db.session.commit()
        return jsonify({"error": str(exc)}), 500

    all_records = []
    for round_item in round_outputs:
        all_records.extend(round_item["records"])

    db.session.add(Log(job_id=job_id, message=f"[AI多轮验证] {page.url} -> {len(round_outputs)} 轮 / {len(all_records)} 条结果"))
    for round_item in round_outputs:
        _persist_runtime_verifications(
            job_id,
            round_item["records"],
            batch_id=batch_id,
            source="ai_multi_round",
            report_meta={
                "reason": ai_plan["reason"],
                "preferred_vector": round_item["vector"],
                "preferred_payload": round_item["payload"],
                "mode": mode,
                "round_index": round_item["round_index"],
                "round_label": round_item["round_label"],
                "candidate_id": round_item["candidate_id"],
                "round_reason": round_item["reason"],
                "plan_provider": ai_plan["provider"],
            },
        ) # 保存每轮验证结果
    db.session.commit()

    reports = _build_runtime_reports(
        DynamicVerification.query.filter_by(job_id=job_id, page_url=page.url).order_by(DynamicVerification.id.desc()).all(),
        source="ai_multi_round",
    ) # 聚合 AI 验证报告
    current_report = _select_runtime_report(reports, batch_id) # 取当前批次报告
    return jsonify(
        {
            "ok": True,
            "batch_id": batch_id,
            "mode": mode,
            "plan_provider": ai_plan["provider"],
            "plan_reason": ai_plan["reason"],
            "rounds": [
                {
                    "round_index": item["round_index"],
                    "round_label": item["round_label"],
                    "candidate_id": item["candidate_id"],
                    "reason": item["reason"],
                    "vector": item["vector"],
                    "payload": item["payload"],
                    "context": item["context"],
                    "result_count": len(item["records"]),
                }
                for item in round_outputs
            ],
            "report": current_report,
        }
    )


@api_bp.delete("/jobs/<job_id>/pages/ai-validate-reports/<batch_id>")
def delete_ai_validate_report(job_id: str, batch_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    page_url = str(request.args.get("url") or "").strip()
    if not page_url:
        return jsonify({"error": "url required"}), 400

    records = (
        DynamicVerification.query.filter_by(job_id=job_id, page_url=page_url)
        .order_by(DynamicVerification.id.asc())
        .all()
    )
    matched: list[DynamicVerification] = []
    for item in records:
        detail = _parse_dynamic_evidence(item.evidence)
        if detail.get("source") != "ai_multi_round":
            continue
        detail_batch_id = detail.get("batch_id")
        legacy_batch_id = f"legacy-{item.id}"
        if batch_id == detail_batch_id or (detail_batch_id is None and batch_id == legacy_batch_id):
            matched.append(item)

    if not matched:
        return jsonify({"error": "report not found"}), 404

    for item in matched:
        db.session.delete(item)
    db.session.add(Log(job_id=job_id, message=f"[AI多轮验证] 删除验证报告 {batch_id}，共 {len(matched)} 条记录"))
    db.session.commit()
    return jsonify({"ok": True, "deleted": len(matched), "batch_id": batch_id})


@api_bp.post("/jobs/<job_id>/pages/ai-explain")
def explain_page_workbench(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    page_url = str(payload.get("url") or "").strip()
    audience = str(payload.get("audience") or "developer").strip().lower()
    batch_id = str(payload.get("batch_id") or "").strip()
    compare_batch_id = str(payload.get("compare_batch_id") or "").strip()
    if not page_url:
        return jsonify({"error": "url required"}), 400

    page = Page.query.filter_by(job_id=job_id, url=page_url).order_by(Page.id.desc()).first()
    if page is None:
        return jsonify({"error": "page not found"}), 404

    findings = Finding.query.filter_by(job_id=job_id, url=page.url).order_by(Finding.id.asc()).all()
    verifications = (
        DynamicVerification.query.filter_by(job_id=job_id, page_url=page.url)
        .order_by(DynamicVerification.id.desc())
        .all()
    )
    manual_retests = [item for item in verifications if _parse_dynamic_evidence(item.evidence).get("source") == "manual_retest"]
    reports = _build_manual_retest_reports(manual_retests) # 聚合手工复测报告
    current_report = _select_manual_retest_report(reports, batch_id) # 当前报告
    compare_report = _select_manual_retest_report(reports, compare_batch_id) # 对比报告
    input_profile = _build_page_input_profile(page) # 页面输入面
    risk_summary = _build_page_risk_summary(findings, verifications, input_profile) # 页面风险摘要

    page_context = {
        "url": page.url,
        "status_code": page.status_code,
        "content_type": page.content_type,
        "input_profile": input_profile,
        "risk_summary": risk_summary,
        "related_findings": _serialize_workbench_findings(findings)[:8],
    }
    report_context = {
        "current_report": current_report,
        "compare_report": compare_report,
    }

    analyzer = get_analyzer() # 获取 AI 分析器
    result = analyzer.explain_workbench(page_context, report_context, audience) # 生成解释
    if not result.get("success"):
        db.session.add(Log(job_id=job_id, message=f"[AI解释] 页面解释失败：{page.url} - {result.get('error')}"))
        db.session.commit()
        return jsonify({"error": str(result.get("error") or "AI explanation failed")}), 500

    db.session.add(Log(job_id=job_id, message=f"[AI解释] 页面解释成功：{page.url}"))
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "audience": audience,
            "page_url": page.url,
            "batch_id": current_report["batch_id"] if current_report else None,
            "compare_batch_id": compare_report["batch_id"] if compare_report else None,
            "explanation": result["explanation"],
        }
    )


def _serialize_ai_payload_reports(job_id: str, page_url: str) -> list[dict[str, object]]:
    reports = (
        AIPayloadReport.query
        .filter_by(job_id=job_id, page_url=page_url)
        .order_by(AIPayloadReport.id.desc())
        .limit(10)
        .all()
    )
    result: list[dict[str, object]] = []
    for r in reports:
        try:
            payloads = json.loads(r.payloads_json)
        except (json.JSONDecodeError, TypeError):
            payloads = []
        result.append({
            "id": r.id,
            "mode": r.mode,
            "finding_kind": r.finding_kind,
            "finding_title": r.finding_title,
            "payloads": payloads,
            "created_at": _to_beijing_iso(r.created_at),
        })
    return result


@api_bp.post("/jobs/<job_id>/pages/ai-generate-payload")
def ai_generate_payload_page(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True, silent=True) or {}
    page_url = str(payload.get("url") or "").strip()
    finding_kind = str(payload.get("finding_kind") or "").strip()
    finding_title = str(payload.get("finding_title") or "").strip()
    mode = str(payload.get("mode") or "exploit").strip().lower()

    if mode not in {"probe", "exploit"}:
        return jsonify({"error": "invalid mode"}), 400
    if not page_url:
        return jsonify({"error": "url required"}), 400

    page = Page.query.filter_by(job_id=job_id, url=page_url).order_by(Page.id.desc()).first()
    if page is None:
        return jsonify({"error": "page not found"}), 404

    findings = Finding.query.filter_by(job_id=job_id, url=page.url).order_by(Finding.id.asc()).all()

    target_finding = None
    if finding_kind and finding_title:
        target_finding = next(
            (f for f in findings if f.kind == finding_kind and f.title == finding_title),
            None,
        )
    if target_finding is None and findings:
        target_finding = max(findings, key=lambda f: _severity_score(f.severity))

    if target_finding is None:
        return jsonify({"error": "no finding available for payload generation"}), 400

    evidence = _parse_evidence(target_finding.evidence) # 解析静态证据
    finding_context: dict[str, object] = {
        "kind": target_finding.kind,
        "title": target_finding.title,
        "severity": target_finding.severity,
        "evidence": {
            "source": evidence.get("source"),
            "sink": evidence.get("sink"),
            "path": evidence.get("path"),
            "flow_display": evidence.get("flow_display"),
            "snippet": str(evidence.get("snippet") or "")[:500],
            "label": evidence.get("label"),
            "line": evidence.get("line"),
        },
    }

    verifications = DynamicVerification.query.filter_by(
        job_id=job_id, page_url=page.url,
    ).order_by(DynamicVerification.id.desc()).limit(5).all()
    for v in verifications:
        detail = _parse_dynamic_evidence(v.evidence)
        if detail.get("reflection_context"):
            finding_context["reflection_context"] = detail["reflection_context"]
            finding_context["context_hint"] = detail.get("context_hint")
            break

    analyzer = get_analyzer() # 获取 AI 分析器
    result = analyzer.generate_payloads(finding_context, page.content or "", mode) # 生成 payload
    if not result.get("success"):
        db.session.add(Log(job_id=job_id, message=f"[AI生成Payload] 失败：{page.url} - {result.get('error')}"))
        db.session.commit()
        return jsonify({"error": str(result.get("error") or "AI payload generation failed")}), 500

    ai_content = result["payloads"]["content"]
    try:
        parsed = json.loads(ai_content) # 解析 AI JSON 输出
        generated = parsed.get("payloads") or []
    except (json.JSONDecodeError, TypeError):
        generated = [{"payload": ai_content, "vector": "", "context": "", "reason": "AI 原始输出"}]

    for item in generated:
        item["payload"] = unquote(str(item.get("payload") or ""))

    report = AIPayloadReport(
        job_id=job_id,
        page_url=page.url,
        finding_kind=target_finding.kind,
        finding_title=target_finding.title,
        mode=mode,
        payloads_json=json.dumps(generated, ensure_ascii=False),
    )
    db.session.add(report) # 保存 AI payload 历史
    db.session.add(Log(job_id=job_id, message=f"[AI生成Payload] 成功：{page.url} / 模式：{mode} / 生成 {len(generated)} 个 payload"))
    db.session.commit()

    return jsonify({
        "ok": True,
        "report_id": report.id,
        "mode": mode,
        "page_url": page.url,
        "finding": {
            "kind": target_finding.kind,
            "title": target_finding.title,
            "severity": target_finding.severity,
        },
        "payloads": generated,
    })


@api_bp.get("/jobs/<job_id>/ai-report")
def get_ai_report(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    reports = AIReport.query.filter_by(job_id=job_id).order_by(AIReport.id.asc()).all()
    return jsonify([_serialize_ai_report(r) for r in reports])


@api_bp.get("/pages/<page_id>")
def get_page_detail(page_id: int) -> Response:
    page: Page | None = db.session.get(Page, page_id)
    if page is None:
        return jsonify({"error": "not found"}), 404

    return jsonify(
        {
            "id": page.id,
            "job_id": page.job_id,
            "url": page.url,
            "status_code": page.status_code,
            "content_type": page.content_type,
            "content": page.content,
            "sha256": page.sha256,
            "fetched_at": _to_beijing_iso(page.fetched_at),
        }
    )


def _build_report_payload(job: Job, include_export_details: bool = False) -> dict[str, object]:
    job_id = job.id
    pages_count = db.session.query(func.count(Page.id)).filter_by(job_id=job_id).scalar() or 0 # 页面数量
    raw_findings = Finding.query.filter_by(job_id=job_id).order_by(Finding.id.asc()).all() # 原始风险点
    logs = Log.query.filter_by(job_id=job_id).order_by(Log.id.desc()).limit(500).all() # 最近日志
    pages_query = Page.query.filter_by(job_id=job_id).order_by(Page.id.desc())
    pages = pages_query.all() if include_export_details else pages_query.limit(100).all()
    verifications = DynamicVerification.query.filter_by(job_id=job_id).order_by(DynamicVerification.id.asc()).all()
    status_records = FindingStatus.query.filter_by(job_id=job_id).all()
    ai_reports = AIReport.query.filter_by(job_id=job_id).order_by(AIReport.id.asc()).all()

    grouped_findings = _build_grouped_findings(raw_findings, verifications, status_records) # 合并同类风险
    severity_stats = Counter(item["severity"] for item in grouped_findings)
    kind_stats = Counter(item["kind"] for item in grouped_findings)
    page_risk = _top_risk_pages(grouped_findings)
    verification_stats = Counter(item.status for item in verifications)

    pages.reverse()
    logs.reverse()

    serialized_verifications = [_serialize_verification(item) for item in verifications] # 序列化验证结果

    payload = {
        "export_generated_at": _to_beijing_iso(datetime.utcnow()),
        "job": {
            "id": job.id,
            "target_url": job.target_url,
            "status": job.status,
            "error": job.error,
            "created_at": _to_beijing_iso(job.created_at),
            "started_at": _to_beijing_iso(job.started_at),
            "finished_at": _to_beijing_iso(job.finished_at),
        },
        "stats": {
            "pages": pages_count,
            "findings": len(grouped_findings),
            "instances": len(raw_findings),
            "severity": dict(severity_stats),
            "severity_labels": {key: _severity_label(key) for key in severity_stats},
            "by_kind": dict(kind_stats),
        },
        "summary": {
            "top_risk_pages": page_risk,
        },
        "dynamic_verification": {
            "enabled": get_bool("DYNAMIC_VERIFY_ENABLED", False),
            "stats": dict(verification_stats),
            "results": serialized_verifications,
            "successful_payloads": _build_successful_payloads(serialized_verifications),
        },
        "ai_reports": [_serialize_ai_report(item) for item in ai_reports],
        "pages": [
            {
                "id": p.id,
                "url": p.url,
                "status_code": p.status_code,
                "content_type": p.content_type,
                "sha256": p.sha256,
                "fetched_at": _to_beijing_iso(p.fetched_at),
            }
            for p in pages
        ],
        "findings": grouped_findings,
        "logs": [{"message": l.message, "ts": _to_beijing_ts(l.created_at)} for l in logs],
    }

    if include_export_details:
        export_details = _build_export_detail_payload(pages, raw_findings, verifications)
        payload["page_workbenches"] = export_details["page_workbenches"]
        payload["manual_retest_reports"] = export_details["manual_retest_reports"]
        payload["ai_multi_round_reports"] = export_details["ai_multi_round_reports"]
        payload["stats"]["manual_retest_reports"] = len(export_details["manual_retest_reports"])
        payload["stats"]["ai_multi_round_reports"] = len(export_details["ai_multi_round_reports"])

    return payload


def _build_export_detail_payload(
    pages: list[Page],
    findings: list[Finding],
    verifications: list[DynamicVerification],
) -> dict[str, object]:
    findings_by_url: dict[str, list[Finding]] = {}
    for item in findings:
        findings_by_url.setdefault(item.url, []).append(item)

    verifications_by_url: dict[str, list[DynamicVerification]] = {}
    for item in verifications:
        verifications_by_url.setdefault(item.page_url, []).append(item)

    page_workbenches: list[dict[str, object]] = []
    manual_retest_reports: list[dict[str, object]] = []
    ai_multi_round_reports: list[dict[str, object]] = []

    for page in pages:
        page_findings = findings_by_url.get(page.url, [])
        page_verifications = verifications_by_url.get(page.url, [])
        input_profile = _build_page_input_profile(page)
        risk_summary = _build_page_risk_summary(page_findings, page_verifications, input_profile)
        related_findings = _serialize_workbench_findings(page_findings)
        dynamic_results = [
            item
            for item in page_verifications
            if _parse_dynamic_evidence(item.evidence).get("source") not in {"manual_retest", "ai_multi_round"}
        ]
        manual_retests = [
            item for item in page_verifications if _parse_dynamic_evidence(item.evidence).get("source") == "manual_retest"
        ]
        ai_multi_round = [
            item for item in page_verifications if _parse_dynamic_evidence(item.evidence).get("source") == "ai_multi_round"
        ]
        page_manual_reports = [_decorate_runtime_report(item) for item in _build_manual_retest_reports(manual_retests)]
        page_ai_reports = [
            _decorate_runtime_report(item) for item in _build_runtime_reports(ai_multi_round, source="ai_multi_round")
        ]
        manual_retest_reports.extend(page_manual_reports)
        ai_multi_round_reports.extend(page_ai_reports)

        page_workbenches.append(
            {
                "page": {
                    "id": page.id,
                    "job_id": page.job_id,
                    "url": page.url,
                    "status_code": page.status_code,
                    "content_type": page.content_type,
                    "sha256": page.sha256,
                    "fetched_at": _to_beijing_iso(page.fetched_at),
                },
                "input_profile": input_profile,
                "risk_summary": risk_summary,
                "repair_suggestions": _build_page_repair_suggestions(page_findings, input_profile),
                "related_findings": related_findings,
                "dynamic_result_count": len(dynamic_results),
                "dynamic_results": [_serialize_verification(item) for item in dynamic_results[:20]],
                "retest_strategy": _build_page_retest_strategy(page, page_findings, input_profile),
                "latest_manual_retest_report": page_manual_reports[0] if page_manual_reports else None,
                "manual_retest_reports": page_manual_reports[:10],
                "latest_ai_multi_round_report": page_ai_reports[0] if page_ai_reports else None,
                "ai_multi_round_reports": page_ai_reports[:10],
            }
        )

    manual_retest_reports.sort(key=lambda item: int(item.get("created_at_ts") or 0), reverse=True)
    ai_multi_round_reports.sort(key=lambda item: int(item.get("created_at_ts") or 0), reverse=True)
    return {
        "page_workbenches": page_workbenches,
        "manual_retest_reports": manual_retest_reports,
        "ai_multi_round_reports": ai_multi_round_reports,
    }


def _decorate_runtime_report(report: dict[str, object]) -> dict[str, object]:
    results = report.get("results") or []
    first = results[0] if results else {}
    target_urls = sorted({str(item.get("target_url") or "") for item in results if item.get("target_url")})
    contexts = sorted(
        {
            str(item.get("reflection_context_label") or "")
            for item in results
            if item.get("reflection_context_label")
        }
    )
    return {
        **report,
        "page_id": first.get("page_id"),
        "page_url": first.get("page_url") or "",
        "target_urls": target_urls,
        "reflection_hits": sum(1 for item in results if item.get("reflection_found")),
        "contexts": contexts,
    }




def _parse_evidence(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return {
                "line": payload.get("line"),
                "label": payload.get("label"),
                "snippet": payload.get("snippet") or raw,
                "source": payload.get("source"),
                "path": payload.get("path") if isinstance(payload.get("path"), list) else [],
                "sink": payload.get("sink"),
                "flow_display": payload.get("flow_display"),
            }
    except Exception:
        pass
    return {"line": None, "label": None, "snippet": raw, "source": None, "path": [], "sink": None, "flow_display": None}


def _finding_family(kind: str, title: str, payload: dict[str, object]) -> tuple[str, str]:
    snippet = str(payload.get("snippet") or "").lower()

    if kind in {"inline_event_handler", "javascript_redirection"} and any(
        token in snippet for token in ("location.href", "window.location", "location.assign", "location.replace")
    ):
        return ("inline_event_navigation", "内联事件跳转风险")

    if kind in {"javascript_protocol", "data_protocol", "iframe_srcdoc"}:
        return ("executable_attribute", "可执行属性注入风险")

    if kind in {"tainted_source", "source_sink_flow", "ast_data_flow"}:
        source = str(payload.get("source") or "")
        if source:
            return ("data_flow_source", f"数据流风险：{source}")
        return ("data_flow_source", "数据流风险")

    if kind == "dom_sink":
        sink = str(payload.get("sink") or payload.get("label") or "")
        if sink:
            return ("dom_sink_group", f"DOM Sink：{sink}")
        return ("dom_sink_group", "DOM Sink 风险")

    return (kind, title)


def _explain_finding(kind: str, severity: str) -> tuple[str, str, str, str]:
    if kind == "inline_event_navigation":
        return (
            "页面通过内联事件直接触发跳转逻辑，这类写法常与 onclick 拼接脚本或路径混用，风险应整体审视。",
            "high",
            "建议把跳转逻辑移到 addEventListener 或受控函数中，避免在 HTML 属性里直接操作 location。",
            "html_attr",
        )
    if kind == "data_flow_source":
        return (
            "页面中识别到用户可控输入沿数据流路径到达危险 Sink，存在明确的 DOM XSS 风险。",
            "high",
            "优先检查变量传播链上的赋值和拼接逻辑，确认是否需要改为安全输出或增加中间清洗。",
            "flow",
        )
    if kind == "dom_sink_group":
        return (
            "页面使用了可直接执行或拼接 HTML 的危险 Sink，若输入可控则可能触发脚本执行。",
            "high" if severity == "high" else "medium",
            "优先改用 textContent、setAttribute 等安全写法，避免把未经处理的内容写入 HTML。",
            "script_snippet",
        )
    if kind == "source_sink_flow":
        return (
            "页面中同时出现潜在输入源和危险输出点，存在较强的 DOM XSS 风险信号。",
            "high",
            "优先检查 URL、Cookie 等数据是否直接流入 innerHTML、document.write 等危险位置。",
            "flow",
        )
    if kind == "ast_data_flow":
        return (
            "脚本中识别到了更明确的变量赋值链，说明用户可控输入已经沿着脚本逻辑流向危险 Sink，比普通关键字共现更接近真实数据流。",
            "high",
            "优先检查这条变量传播链上的赋值和拼接逻辑，确认是否需要改为安全输出或增加中间清洗。",
            "flow",
        )
    if kind == "dom_sink":
        return (
            "页面使用了可直接执行或拼接 HTML 的危险 Sink，若输入可控则可能触发脚本执行。",
            "high" if severity == "high" else "medium",
            "优先改用 textContent、setAttribute 等安全写法，避免把未经处理的内容写入 HTML。",
            "script_snippet",
        )
    if kind == "inline_event_handler":
        return (
            "页面存在内联事件处理器，这类写法会放大注入后的脚本执行风险。",
            "high",
            "建议改用 addEventListener 绑定事件，并避免把动态数据直接拼进事件属性。",
            "html_attr",
        )
    if kind in {"javascript_protocol", "data_protocol", "iframe_srcdoc"}:
        return (
            "页面存在可执行协议或 srcdoc 这类高风险属性，通常会直接提升利用可能性。",
            "high",
            "建议移除 javascript:、data:text/html、srcdoc 等执行入口，改为普通链接或受控跳转。",
            "html_attr",
        )
    if kind == "tainted_source":
        return (
            "页面读取了潜在用户可控输入，但当前尚未确认是否进入危险输出位置。",
            "low",
            "继续核查这些输入是否流向 innerHTML、document.write、eval 等危险位置。",
            "summary",
        )
    if kind == "javascript_redirection":
        return (
            "页面存在基于 JavaScript 的跳转逻辑，需要确认是否会拼接用户输入导致开放跳转或脚本注入。",
            "low",
            "建议统一封装跳转逻辑，并限制 location 赋值来源。",
            "summary",
        )
    if kind == "anomaly":
        return (
            "页面脚本标签数量异常偏多，可能增加攻击面，也可能意味着页面逻辑较复杂。",
            "low",
            "建议优先复核该页面的脚本加载和动态渲染逻辑。",
            "summary",
        )
    return (
        "页面存在需要进一步人工复核的潜在风险信号。",
        "medium",
        "建议结合页面上下文、输入来源和输出位置继续确认风险。",
        "summary",
    )


def _top_risk_pages(findings: list[dict[str, object]]) -> list[dict[str, object]]:
    page_scores: dict[str, dict[str, object]] = {}
    for finding in findings:
        score = _severity_score(str(finding["severity"]))
        bucket = page_scores.setdefault(
            str(finding["url"]),
            {"url": finding["url"], "score": 0, "findings": 0, "highest_severity": "low"},
        )
        bucket["score"] += score
        bucket["findings"] += 1
        if score > _severity_score(str(bucket["highest_severity"])):
            bucket["highest_severity"] = finding["severity"]
    return sorted(page_scores.values(), key=lambda item: (-int(item["score"]), -int(item["findings"]), str(item["url"])))[:10]


def _build_grouped_findings(
    findings: list[Finding],
    verifications: list[DynamicVerification],
    status_records: list[FindingStatus],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], dict[str, object]] = {}
    for finding in findings:
        payload = _parse_evidence(finding.evidence)
        payload["url"] = finding.url
        family_key, family_title = _finding_family(finding.kind, finding.title, payload)
        group = groups.setdefault(
            (family_key, family_title),
            {
                "kind": family_key,
                "severity": finding.severity,
                "title": family_title,
                "created_at": _to_beijing_iso(finding.created_at),
                "instances": [],
                "urls": set(),
                "member_kinds": set(),
            },
        )
        group["instances"].append(payload)
        group["urls"].add(finding.url)
        group["member_kinds"].add(finding.kind)
        if _severity_score(finding.severity) > _severity_score(str(group["severity"])):
            group["severity"] = finding.severity

    status_map = {(item.finding_kind, item.finding_title): item for item in status_records}
    grouped: list[dict[str, object]] = []
    for group in groups.values():
        reason, confidence, recommendation, evidence_type = _explain_finding(group["kind"], group["severity"])
        _kind_priority = {"ast_data_flow": 0, "source_sink_flow": 1, "tainted_source": 2, "dom_sink": 3}
        instances = sorted(
            group["instances"],
            key=lambda item: (_kind_priority.get(str(item.get("kind", "")), 9), item.get("line") or 0),
        )
        urls = sorted(group["urls"])
        lines = [str(item["line"]) for item in instances if item.get("line")]
        summary = f"共命中 {len(instances)} 处，涉及 {len(urls)} 个页面"
        if lines:
            summary += f"，行号 {', '.join(lines[:8])}"
        status_record = status_map.get((str(group["kind"]), str(group["title"])))
        linked_verifications = _match_verifications_for_group(instances, urls, verifications)
        verdict = _final_assessment(str(group["severity"]), linked_verifications)
        grouped.append(
            {
                "url": urls[0] if urls else "",
                "urls": urls,
                "page_count": len(urls),
                "kind": group["kind"],
                "member_kinds": sorted(group["member_kinds"]),
                "severity": group["severity"],
                "severity_label": _severity_label(str(group["severity"])),
                "title": group["title"],
                "summary": summary,
                "evidence": unquote(instances[0].get("snippet") or ""),
                "instances": instances,
                "instance_count": len(instances),
                "reason": reason,
                "confidence": confidence,
                "confidence_label": _confidence_label(confidence),
                "recommendation": recommendation,
                "evidence_type": evidence_type,
                "final_assessment": verdict["value"],
                "final_assessment_label": verdict["label"],
                "final_assessment_reason": verdict["reason"],
                "review_status": status_record.status if status_record else "open",
                "review_status_label": _review_status_label(status_record.status if status_record else "open"),
                "review_note": status_record.note if status_record else None,
                "matched_verifications": len(linked_verifications),
                "linked_verification_results": [_serialize_verification(item) for item in linked_verifications],
                "created_at": group["created_at"],
            }
        )

    grouped.extend(_build_dynamic_only_findings(grouped, verifications))

    return sorted(grouped, key=lambda item: (_severity_score(item["severity"]), item["title"]), reverse=True)


def _match_verifications(urls: list[str], verifications: list[DynamicVerification]) -> list[DynamicVerification]:
    url_set = {url for url in urls if url}
    return [item for item in verifications if item.page_url in url_set]


def _match_verifications_for_group(
    instances: list[dict[str, object]],
    urls: list[str],
    verifications: list[DynamicVerification],
) -> list[DynamicVerification]:
    candidates = _match_verifications(urls, verifications)
    vectors = _expected_vectors_for_instances(instances)
    if not vectors:
        return candidates
    return [item for item in candidates if item.vector in vectors]


def _expected_vectors_for_instances(instances: list[dict[str, object]]) -> set[str]:
    vectors: set[str] = set()
    for item in instances:
        text = " ".join(
            [
                str(item.get("label") or ""),
                str(item.get("snippet") or ""),
                str(item.get("source") or ""),
                str(item.get("flow_display") or ""),
            ]
        ).lower()
        if any(token in text for token in ("location.search", "document.url", "location.href", "query")):
            vectors.add("query")
        if any(token in text for token in ("location.hash", "hashchange")):
            vectors.add("hash")
        if any(token in text for token in ("form", "input", "textarea", "select")):
            vectors.add("form")
    return vectors


def _build_verification_construction(
    page_url: str,
    target_url: str,
    vector: str,
    parameter_name: str | None,
    payload: str,
    reflection_snippet: str | None,
) -> dict[str, object]:
    page_url = str(page_url or "").strip()
    target_url = str(target_url or "").strip()
    vector = str(vector or "").strip().lower()
    parameter_name = str(parameter_name or "").strip()
    payload = str(payload or "").strip()
    snippet = str(reflection_snippet or "").strip()

    result: dict[str, object] = {
        "before_target": page_url,
        "after_target": target_url,
        "request_construction": "",
        "markup_construction": "",
        "before_after_summary": "",
    }

    if vector == "query":
        result["request_construction"] = f"将参数 {parameter_name or '-'} 替换为 payload 后访问目标地址。"
        result["before_after_summary"] = f"原始页面地址与注入后地址的差异主要体现在查询参数 {parameter_name or '-'}。"
        if target_url:
            split_result = urlsplit(target_url)
            pairs = parse_qsl(split_result.query, keep_blank_values=True)
            matched = next((f"{key}={value}" for key, value in pairs if not parameter_name or key == parameter_name), "")
            if matched:
                result["mutated_part"] = matched
    elif vector == "form":
        field_names = [name.strip() for name in parameter_name.split(",") if name.strip()] if parameter_name else []
        pseudo_fields = "\n".join([f'<input name="{name}" value="{payload}">' for name in field_names[:5]])
        result["request_construction"] = f"将表单字段 {', '.join(field_names) if field_names else '-'} 统一填入 payload 后提交到目标地址。"
        result["before_after_summary"] = "原始页面先解析表单，再把可提交字段替换为同一 payload 后发起提交。"
        if pseudo_fields:
            result["markup_construction"] = f'<form action="{target_url or page_url}" method="post">\n{pseudo_fields}\n</form>'
    elif vector == "hash":
        result["request_construction"] = "保持原始页面地址不变，仅把 payload 拼接到 URL 的 # 片段后。"
        result["before_after_summary"] = "原始地址与注入后地址的差异主要体现在 hash 片段。"
    else:
        result["request_construction"] = "系统把 payload 带入当前输入向量后请求目标地址，再观察页面返回结果。"
        result["before_after_summary"] = "原始地址与注入后目标地址之间存在输入构造差异。"

    if snippet:
        result["snippet_before"] = snippet.replace(payload, "[payload]")
        result["snippet_after"] = snippet
    else:
        result["snippet_before"] = ""
        result["snippet_after"] = ""

    return result


def _serialize_verification(item: DynamicVerification) -> dict[str, object]:
    detail = _parse_dynamic_evidence(item.evidence)
    explanation = _explain_dynamic_verification(
        item.vector,
        item.status,
        item.parameter_name,
        detail["detail"],
    )
    construction = _build_verification_construction(
        item.page_url,
        item.target_url,
        item.vector,
        item.parameter_name,
        item.payload,
        detail["reflection_snippet"],
    )
    return {
        "id": item.id,
        "page_id": item.page_id,
        "page_url": item.page_url,
        "target_url": item.target_url,
        "vector": item.vector,
        "parameter_name": item.parameter_name,
        "payload": item.payload,
        "status": item.status,
        "engine": detail["engine"],
        "source": detail["source"],
        "level": explanation["level"],
        "level_label": _dynamic_level_label(explanation["level"]),
        "summary": explanation["summary"],
        "reason": explanation["risk"],
        "recommendation": explanation["recommendation"],
        "evidence": detail["detail"],
        "reflection_found": detail["reflection_found"],
        "reflection_context": detail["reflection_context"],
        "reflection_context_label": _reflection_context_label(detail["reflection_context"]),
        "reflection_snippet": detail["reflection_snippet"],
        "context_hint": detail["context_hint"],
        "batch_id": detail["batch_id"],
        "mode": detail["mode"],
        "round_index": detail["round_index"],
        "round_label": detail["round_label"],
        "candidate_id": detail["candidate_id"],
        "round_reason": detail["round_reason"],
        "created_at": _to_beijing_iso(item.created_at),
        "construction": construction,
    }


def _build_successful_payloads(results: list[dict[str, object]]) -> list[dict[str, object]]:
    successful: list[dict[str, object]] = []
    seen: set[str] = set()

    def _sort_key(item: dict[str, object]) -> tuple[int, int, str]:
        level = str(item.get("level") or "")
        return (
            0 if level == "confirmed" else 1,
            0 if item.get("reflection_found") else 1,
            str(item.get("created_at") or ""),
        )

    for item in sorted(results, key=_sort_key):
        level = str(item.get("level") or "")
        reflection_found = bool(item.get("reflection_found"))
        if level != "confirmed" and not reflection_found:
            continue

        payload = str(item.get("payload") or "").strip()
        if not payload:
            continue

        vector = str(item.get("vector") or "").strip()
        parameter_name = str(item.get("parameter_name") or "").strip()
        target_url = str(item.get("target_url") or "").strip()
        dedupe_key = "||".join([payload, vector, parameter_name, target_url])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        context_label = str(item.get("reflection_context_label") or "").strip()
        reason = str(item.get("reason") or "").strip()
        summary = str(item.get("summary") or "").strip()
        explanation_parts = []
        if context_label:
            explanation_parts.append(f"该 payload 在{context_label}上下文中出现回显，说明输入已进入页面可利用位置。")
        elif reflection_found:
            explanation_parts.append("该 payload 已出现可识别回显，说明输入链路真实可达。")
        if reason:
            explanation_parts.append(reason)
        elif summary:
            explanation_parts.append(summary)

        successful.append(
            {
                "id": item.get("id"),
                "page_url": item.get("page_url"),
                "target_url": target_url,
                "vector": vector,
                "parameter_name": parameter_name,
                "payload": payload,
                "level": level,
                "level_label": item.get("level_label"),
                "summary": summary,
                "reason": reason,
                "recommendation": item.get("recommendation"),
                "reflection_found": reflection_found,
                "reflection_context": item.get("reflection_context"),
                "reflection_context_label": context_label,
                "reflection_snippet": item.get("reflection_snippet"),
                "context_hint": item.get("context_hint"),
                "created_at": item.get("created_at"),
                "construction": _build_verification_construction(
                    str(item.get("page_url") or ""),
                    target_url,
                    vector,
                    parameter_name,
                    payload,
                    item.get("reflection_snippet"),
                ),
                "usage_tip": "建议优先把这个 payload 带入单点复测，继续验证同一向量和参数。",
                "why_it_worked": " ".join(part for part in explanation_parts if part).strip(),
            }
        )

    return successful


def _serialize_ai_report(item: AIReport) -> dict[str, object]:
    return {
        "id": item.id,
        "page_url": item.page_url,
        "summary": item.summary,
        "accuracy": item.accuracy,
        "false_positives": json.loads(item.false_positives) if item.false_positives else [],
        "false_negatives": json.loads(item.false_negatives) if item.false_negatives else [],
        "suggestions": json.loads(item.suggestions) if item.suggestions else [],
        "risk_assessment": item.risk_assessment,
        "full_report": item.full_report,
        "created_at": _to_beijing_iso(item.created_at),
    }


def _serialize_runtime_verification(item) -> dict[str, object]:
    detail = _parse_dynamic_evidence(
        json.dumps(
            {
                "engine": item.engine,
                "detail": item.evidence,
                "reflection_found": item.reflection_found,
                "reflection_context": item.reflection_context,
                "reflection_snippet": item.reflection_snippet,
                "context_hint": item.context_hint,
            },
            ensure_ascii=False,
        )
    )
    explanation = _explain_dynamic_verification(
        item.vector,
        item.status,
        item.parameter_name,
        detail["detail"],
    )
    return {
        "page_id": item.page_id,
        "page_url": item.page_url,
        "target_url": item.target_url,
        "vector": item.vector,
        "parameter_name": item.parameter_name,
        "payload": item.payload,
        "status": item.status,
        "engine": item.engine,
        "source": "manual_retest",
        "level": explanation["level"],
        "level_label": _dynamic_level_label(explanation["level"]),
        "summary": explanation["summary"],
        "risk": explanation["risk"],
        "recommendation": explanation["recommendation"],
        "evidence": detail["detail"],
        "reflection_found": detail["reflection_found"],
        "reflection_context": detail["reflection_context"],
        "reflection_context_label": _reflection_context_label(detail["reflection_context"]),
        "reflection_snippet": detail["reflection_snippet"],
        "context_hint": detail["context_hint"],
        "batch_id": None,
    }


def _persist_runtime_verifications(
    job_id: str,
    records: list[object],
    *,
    batch_id: str | None = None,
    source: str = "manual_retest",
    report_meta: dict[str, object] | None = None,
) -> None:
    for item in records:
        db.session.add(
            DynamicVerification(
                job_id=job_id,
                page_id=item.page_id,
                page_url=item.page_url,
                target_url=item.target_url,
                vector=item.vector,
                parameter_name=item.parameter_name,
                payload=item.payload,
                status=item.status,
                evidence=json.dumps(
                    {
                        "engine": item.engine,
                        "detail": item.evidence,
                        "reflection_found": bool(getattr(item, "reflection_found", False)),
                        "reflection_context": getattr(item, "reflection_context", None),
                        "reflection_snippet": getattr(item, "reflection_snippet", None),
                        "context_hint": getattr(item, "context_hint", None),
                        "source": source,
                        "batch_id": batch_id,
                        "report_reason": (report_meta or {}).get("reason"),
                        "preferred_vector": (report_meta or {}).get("preferred_vector"),
                        "preferred_payload": (report_meta or {}).get("preferred_payload"),
                        "mode": (report_meta or {}).get("mode"),
                        "round_index": (report_meta or {}).get("round_index"),
                        "round_label": (report_meta or {}).get("round_label"),
                        "candidate_id": (report_meta or {}).get("candidate_id"),
                        "round_reason": (report_meta or {}).get("round_reason"),
                        "plan_provider": (report_meta or {}).get("plan_provider"),
                    },
                    ensure_ascii=False,
                ),
            )
        )


def _build_page_input_profile(page: Page) -> dict[str, object]:
    split_result = urlsplit(page.url)
    query_params = sorted({name for name, _ in parse_qsl(split_result.query, keep_blank_values=True)})
    content = page.content or ""
    content_lower = content.lower()
    forms: list[dict[str, object]] = []

    try:
        if content:
            document = lxml_html.fromstring(content)
            for form in document.xpath("//form")[:5]:
                fields: list[str] = []
                for field in form.xpath(".//input|.//textarea|.//select"):
                    field_name = (field.get("name") or "").strip()
                    field_type = (field.get("type") or "").lower()
                    if not field_name or field_type in {"submit", "button", "reset", "image", "file"}:
                        continue
                    if field_name not in fields:
                        fields.append(field_name)
                forms.append(
                    {
                        "action": (form.get("action") or page.url).strip() or page.url,
                        "method": (form.get("method") or "get").strip().lower() or "get",
                        "fields": fields[:8],
                    }
                )
    except Exception:
        forms = []

    source_hints: list[str] = []
    source_tokens = {
        "location.search": "location.search",
        "location.hash": "location.hash",
        "document.url": "document.URL",
        "location.href": "location.href",
        "document.cookie": "document.cookie",
        "localstorage": "localStorage",
        "sessionstorage": "sessionStorage",
        "postmessage": "postMessage",
    }
    for token, label in source_tokens.items():
        if token in content_lower:
            source_hints.append(label)

    inline_event_count = len(re.findall(r"\son[a-z0-9_-]+\s*=", content, flags=re.IGNORECASE))
    script_blocks = len(re.findall(r"<script\b", content, flags=re.IGNORECASE))

    return {
        "query_params": query_params,
        "forms": forms,
        "uses_hash": "location.hash" in content_lower or "hashchange" in content_lower or "#/" in page.url,
        "source_hints": source_hints,
        "inline_event_count": inline_event_count,
        "script_blocks": script_blocks,
    }


def _build_page_risk_summary(
    findings: list[Finding],
    verifications: list[DynamicVerification],
    input_profile: dict[str, object],
) -> dict[str, object]:
    severity_counter = Counter(str(item.severity) for item in findings)
    kind_counter = Counter(str(item.kind) for item in findings)
    highest_severity = "low"
    if severity_counter:
        highest_severity = max(severity_counter, key=_severity_score)

    risky_api_hints: list[str] = []
    kinds = set(kind_counter.keys())
    if {"dom_sink", "source_sink_flow", "ast_data_flow"} & kinds:
        risky_api_hints.append("危险 DOM 写入 / 数据流")
    if {"javascript_protocol", "data_protocol", "iframe_srcdoc"} & kinds:
        risky_api_hints.append("可执行协议 / 文档入口")
    if {"inline_event_handler", "inline_event_navigation"} & kinds or int(input_profile.get("inline_event_count") or 0) > 0:
        risky_api_hints.append("内联事件处理逻辑")
    if "javascript_redirection" in kinds:
        risky_api_hints.append("客户端跳转逻辑")

    severity_breakdown = [
        {
            "key": key,
            "label": _severity_label(key),
            "count": count,
        }
        for key, count in sorted(severity_counter.items(), key=lambda item: -_severity_score(item[0]))
    ]
    kind_breakdown = [
        {
            "key": key,
            "label": _finding_kind_zh(key),
            "count": count,
        }
        for key, count in sorted(kind_counter.items(), key=lambda item: (-item[1], item[0]))
    ]

    verified_count = sum(1 for item in verifications if item.status == "verified")
    return {
        "total_findings": len(findings),
        "highest_severity": highest_severity,
        "highest_severity_label": _severity_label(highest_severity),
        "severity_breakdown": severity_breakdown,
        "kind_breakdown": kind_breakdown,
        "has_dynamic_verification": bool(verifications),
        "dynamic_result_count": len(verifications),
        "verified_result_count": verified_count,
        "inline_event_hits": sum(
            count for kind, count in kind_counter.items() if kind in {"inline_event_handler", "inline_event_navigation"}
        ),
        "dom_sink_hits": sum(count for kind, count in kind_counter.items() if kind in {"dom_sink", "source_sink_flow", "ast_data_flow"}),
        "risky_api_hints": risky_api_hints,
    }


def _build_page_repair_suggestions(findings: list[Finding], input_profile: dict[str, object]) -> list[str]:
    suggestions: list[str] = []
    kinds = {item.kind for item in findings}
    if {"dom_sink", "source_sink_flow", "ast_data_flow"} & kinds:
        suggestions.append("优先检查 innerHTML、document.write、insertAdjacentHTML 等危险 DOM 写入点，能改成 textContent 或结构化 DOM API 就不要继续拼接 HTML。")
    if {"inline_event_handler", "inline_event_navigation"} & kinds or int(input_profile.get("inline_event_count") or 0) > 0:
        suggestions.append("把 onclick、onload 等内联事件迁移为 addEventListener，避免把动态数据直接拼进事件属性。")
    if {"javascript_protocol", "data_protocol", "iframe_srcdoc"} & kinds:
        suggestions.append("限制 javascript:、data:text/html、srcdoc 这类可执行入口，改成受控白名单或普通跳转方案。")
    if input_profile.get("query_params") or input_profile.get("forms"):
        suggestions.append("对 query 参数和表单回显位置做上下文敏感输出处理，确认文本、属性和脚本上下文分别使用合适的安全写法。")
    if input_profile.get("uses_hash"):
        suggestions.append("如果页面读取 location.hash，优先检查前端路由或片段解析逻辑，避免把 hash 内容直接带入 DOM 或脚本执行链。")
    if not suggestions:
        suggestions.append("当前页面未命中特别集中的修复方向，建议先结合相关发现和源码确认输入来源、输出位置与页面行为。")
    return suggestions[:5]


def _serialize_workbench_findings(findings: list[Finding]) -> list[dict[str, object]]:
    deduped: dict[tuple[str, str], Finding] = {}
    _flow_kinds = {"tainted_source", "source_sink_flow", "ast_data_flow"}
    _flow_priority = {"ast_data_flow": 0, "source_sink_flow": 1, "tainted_source": 2}
    for item in findings:
        if item.kind in _flow_kinds:
            ev = _parse_evidence(item.evidence)
            source = str(ev.get("source") or "")
            key = ("data_flow_source", source)
        elif item.kind == "dom_sink":
            ev = _parse_evidence(item.evidence)
            sink = str(ev.get("sink") or ev.get("label") or "")
            key = ("dom_sink_group", sink)
        else:
            key = (item.kind, item.title)

        current = deduped.get(key)
        if current is None:
            deduped[key] = item
        elif item.kind in _flow_kinds and current.kind in _flow_kinds:
            if _flow_priority.get(item.kind, 9) < _flow_priority.get(current.kind, 9):
                deduped[key] = item
        elif _severity_score(item.severity) > _severity_score(current.severity):
            deduped[key] = item

    ordered = sorted(
        deduped.values(),
        key=lambda item: (-_severity_score(item.severity), item.created_at or datetime.min, item.title),
    )
    result: list[dict[str, object]] = []
    for item in ordered[:20]:
        payload = _parse_evidence(item.evidence)
        result.append(
            {
                "id": item.id,
                "url": item.url,
                "kind": item.kind,
                "kind_display": _finding_kind_display(item.kind),
                "severity": item.severity,
                "severity_label": _severity_label(item.severity),
                "title": item.title,
                "evidence": unquote(str(payload.get("snippet") or item.evidence))[:220],
                "created_at": _to_beijing_iso(item.created_at),
            }
        )
    return result


def _build_page_retest_strategy(
    page: Page,
    findings: list[Finding],
    input_profile: dict[str, object],
) -> dict[str, object]:
    preferred_vector = ""
    reason = "当前页面没有明显单一向量，默认优先使用系统推荐 payload 和自动向量判断。"
    if input_profile.get("forms"):
        preferred_vector = "form"
        reason = "页面存在表单字段，优先尝试 form 向量通常更容易观察到回显和前端拼接行为。"
    elif input_profile.get("query_params"):
        preferred_vector = "query"
        reason = "页面 URL 已包含查询参数，优先尝试 query 向量可以更直接观察参数处理链。"
    elif input_profile.get("uses_hash"):
        preferred_vector = "hash"
        reason = "页面存在 hash 使用痕迹，更适合先观察前端是否读取 location.hash 并带入 DOM。"

    payloads = suggest_payloads_for_page(page, findings)
    return {
        "preferred_vector": preferred_vector,
        "preferred_payload": payloads[0] if payloads else None,
        "reason": reason,
    }


def _locate_finding(
    job_id: str,
    finding_kind: str,
    finding_title: str,
    finding_url: str,
    member_kinds: list[object],
    urls: list[object],
) -> Finding | None:
    direct = (
        Finding.query.filter_by(job_id=job_id, kind=finding_kind, title=finding_title)
        .order_by(Finding.id.asc())
        .first()
    )
    if direct is not None:
        return direct

    normalized_kinds = [str(item).strip() for item in member_kinds if str(item).strip()]
    normalized_urls = [str(item).strip() for item in urls if str(item).strip()]
    if finding_url and finding_url not in normalized_urls:
        normalized_urls.append(finding_url)

    if normalized_kinds and normalized_urls:
        match = (
            Finding.query.filter(
                Finding.job_id == job_id,
                Finding.kind.in_(normalized_kinds),
                Finding.url.in_(normalized_urls),
            )
            .order_by(Finding.id.asc())
            .first()
        )
        if match is not None:
            return match

    if normalized_kinds:
        match = (
            Finding.query.filter(
                Finding.job_id == job_id,
                Finding.kind.in_(normalized_kinds),
            )
            .order_by(Finding.id.asc())
            .first()
        )
        if match is not None:
            return match

    if normalized_urls:
        match = (
            Finding.query.filter(
                Finding.job_id == job_id,
                Finding.url.in_(normalized_urls),
            )
            .order_by(Finding.id.asc())
            .first()
        )
        if match is not None:
            return match

    return (
        Finding.query.filter_by(job_id=job_id, title=finding_title)
        .order_by(Finding.id.asc())
        .first()
    )


def _build_virtual_finding(
    job_id: str,
    finding_url: str,
    finding_kind: str,
    finding_title: str,
    finding_evidence: str,
    finding_severity: str,
) -> Finding:
    return Finding(
        job_id=job_id,
        url=finding_url,
        kind=finding_kind,
        severity=finding_severity,
        title=finding_title,
        evidence=finding_evidence or finding_title,
    )


def _build_dynamic_only_findings(
    grouped_findings: list[dict[str, object]],
    verifications: list[DynamicVerification],
) -> list[dict[str, object]]:
    matched_ids: set[int] = set()
    for finding in grouped_findings:
        for item in finding.get("linked_verification_results", []):
            verification_id = item.get("id")
            if isinstance(verification_id, int):
                matched_ids.add(verification_id)

    dynamic_only: list[dict[str, object]] = []
    for item in verifications:
        if item.status != "verified" or item.id in matched_ids:
            continue

        detail = _parse_dynamic_evidence(item.evidence)
        explanation = _explain_dynamic_verification(
            item.vector,
            item.status,
            item.parameter_name,
            detail["detail"],
        )
        kind = f"dynamic_verified_{item.vector}"
        dynamic_only.append(
            {
                "url": item.page_url,
                "urls": [item.page_url],
                "page_count": 1,
                "kind": kind,
                "kind_zh": _finding_kind_zh(kind),
                "kind_display": _finding_kind_display(kind),
                "member_kinds": [kind],
                "severity": "high",
                "severity_label": _severity_label("high"),
                "title": _dynamic_finding_title(item.vector),
                "summary": explanation["summary"],
                "evidence": detail["detail"] or item.target_url,
                "instances": [
                    {
                        "line": None,
                        "label": item.parameter_name,
                        "snippet": detail["detail"] or item.target_url,
                        "url": item.page_url,
                    }
                ],
                "instance_count": 1,
                "reason": explanation["risk"],
                "confidence": "high",
                "confidence_label": _confidence_label("high"),
                "recommendation": explanation["recommendation"],
                "evidence_type": "dynamic",
                "final_assessment": "confirmed",
                "final_assessment_label": "已动态确认",
                "final_assessment_reason": "该问题由动态验证直接确认，即使静态规则未产出对应漏洞标签，也应进入发现列表。",
                "review_status": "open",
                "review_status_label": _review_status_label("open"),
                "review_note": None,
                "matched_verifications": 1,
                "linked_verification_results": [_serialize_verification(item)],
                "created_at": _to_beijing_iso(item.created_at),
            }
        )
    return dynamic_only


def _dynamic_finding_title(vector: str) -> str:
    return {
        "query": "动态确认查询参数风险",
        "form": "动态确认表单回显风险",
        "hash": "动态确认哈希参数风险",
    }.get(vector, "动态确认输入回显风险")


def _final_assessment(severity: str, verifications: list[DynamicVerification]) -> dict[str, str]:
    if any(item.status == "verified" for item in verifications):
        return {
            "value": "confirmed",
            "label": "已动态确认",
            "reason": "该漏洞关联页面已经存在动态验证成功结果，可以优先视为真实风险。",
        }
    if severity == "high":
        return {
            "value": "needs_review",
            "label": "高危待复核",
            "reason": "静态规则给出了高危信号，但当前没有动态验证成功结果，建议继续人工复核。",
        }
    return {
        "value": "not_triggered",
        "label": "未触发",
        "reason": "当前没有观察到动态验证成功结果，暂时更适合作为待观察风险保留。",
    }


def _review_status_label(status: str) -> str:
    return {
        "open": "待处理",
        "confirmed": "人工确认",
        "false_positive": "误报",
        "fixed": "已修复",
        "ignored": "已忽略",
    }.get(status, "待处理")


def _severity_label(severity: str) -> str:
    return {
        "high": "高危",
        "medium": "中危",
        "low": "低危",
    }.get(severity, severity)


def _confidence_label(confidence: str) -> str:
    return {
        "high": "高",
        "medium": "中",
        "low": "低",
    }.get(confidence, confidence)


def _dynamic_level_label(level: str) -> str:
    return {
        "confirmed": "已确认",
        "suspected": "疑似",
        "error": "错误",
        "not_triggered": "未触发",
    }.get(level, level)


def _finding_kind_zh(kind: str) -> str:
    return {
        "inline_event_navigation": "内联事件跳转风险",
        "data_flow_source": "数据流风险",
        "dom_sink_group": "DOM Sink 风险",
        "inline_event_handler": "内联事件处理器风险",
        "executable_attribute": "可执行属性注入风险",
        "javascript_protocol": "JavaScript 协议执行风险",
        "data_protocol": "Data 协议执行风险",
        "iframe_srcdoc": "iframe srcdoc 注入风险",
        "source_sink_flow": "DOM XSS 数据流风险",
        "ast_data_flow": "脚本数据流危险汇点风险",
        "dom_sink": "危险 DOM 汇点风险",
        "tainted_source": "潜在用户可控输入源",
        "javascript_redirection": "JavaScript 重定向风险",
        "anomaly": "页面异常信号",
        "dynamic_verified_query": "动态确认查询参数风险",
        "dynamic_verified_form": "动态确认表单回显风险",
        "dynamic_verified_hash": "动态确认哈希参数风险",
    }.get(kind, "未知漏洞类型")


def _finding_kind_display(kind: str) -> str:
    return f"{kind}（{_finding_kind_zh(kind)}）"


def _severity_score(severity: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(severity, 1)


def _parse_dynamic_evidence(raw: str | None) -> dict[str, str | None]:
    if not raw:
        return {
            "engine": None,
            "detail": None,
            "source": None,
            "reflection_found": False,
            "reflection_context": None,
            "reflection_snippet": None,
            "context_hint": None,
            "batch_id": None,
            "report_reason": None,
            "preferred_vector": None,
            "preferred_payload": None,
            "mode": None,
            "round_index": None,
            "round_label": None,
            "candidate_id": None,
            "round_reason": None,
            "plan_provider": None,
        }
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return {
                "engine": payload.get("engine"),
                "detail": payload.get("detail") or raw,
                "source": payload.get("source"),
                "reflection_found": bool(payload.get("reflection_found")),
                "reflection_context": payload.get("reflection_context"),
                "reflection_snippet": payload.get("reflection_snippet"),
                "context_hint": payload.get("context_hint"),
                "batch_id": payload.get("batch_id"),
                "report_reason": payload.get("report_reason"),
                "preferred_vector": payload.get("preferred_vector"),
                "preferred_payload": payload.get("preferred_payload"),
                "mode": payload.get("mode"),
                "round_index": payload.get("round_index"),
                "round_label": payload.get("round_label"),
                "candidate_id": payload.get("candidate_id"),
                "round_reason": payload.get("round_reason"),
                "plan_provider": payload.get("plan_provider"),
            }
    except Exception:
        pass
    return {
        "engine": None,
        "detail": raw,
        "source": None,
        "reflection_found": False,
        "reflection_context": None,
        "reflection_snippet": None,
        "context_hint": None,
        "batch_id": None,
        "report_reason": None,
        "preferred_vector": None,
        "preferred_payload": None,
        "mode": None,
        "round_index": None,
        "round_label": None,
        "candidate_id": None,
        "round_reason": None,
        "plan_provider": None,
    }


def _build_manual_retest_reports(verifications: list[DynamicVerification]) -> list[dict[str, object]]:
    return _build_runtime_reports(verifications, source="manual_retest")


def _build_runtime_reports(verifications: list[DynamicVerification], source: str) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for item in sorted(verifications, key=lambda current: current.id, reverse=True):
        detail = _parse_dynamic_evidence(item.evidence)
        if detail.get("source") != source:
            continue
        batch_id = str(detail.get("batch_id") or f"legacy-{item.id}")
        bucket = grouped.setdefault(
            batch_id,
            {
                "batch_id": batch_id,
                "created_at": _to_beijing_iso(item.created_at),
                "created_at_ts": _to_beijing_ts(item.created_at) or 0,
                "reason": detail.get("report_reason"),
                "preferred_vector": detail.get("preferred_vector"),
                "preferred_payload": detail.get("preferred_payload"),
                "mode": detail.get("mode"),
                "plan_provider": detail.get("plan_provider"),
                "results": [],
            },
        )
        bucket["results"].append(_serialize_verification(item))

    reports: list[dict[str, object]] = []
    for bucket in grouped.values():
        results = sorted(
            bucket["results"],
            key=lambda current: (
                int(current.get("round_index") or 0),
                _dynamic_level_sort_key(str(current.get("level"))),
                str(current.get("vector") or ""),
                str(current.get("parameter_name") or ""),
            ),
        )
        statuses = Counter(str(item.get("level") or "") for item in results)
        rounds = _build_runtime_rounds(results)
        verdict = _summarize_runtime_report(statuses, results, source)
        reports.append(
            {
                "batch_id": bucket["batch_id"],
                "created_at": bucket["created_at"],
                "created_at_ts": bucket["created_at_ts"],
                "reason": bucket["reason"],
                "preferred_vector": bucket["preferred_vector"],
                "preferred_payload": bucket["preferred_payload"],
                "mode": bucket["mode"],
                "plan_provider": bucket["plan_provider"],
                "result_count": len(results),
                "verified_count": sum(1 for item in results if item.get("level") == "confirmed"),
                "rounds": rounds,
                "vectors": sorted({str(item.get("vector") or "") for item in results if item.get("vector")}),
                "status_summary": {
                    "confirmed": statuses.get("confirmed", 0),
                    "suspected": statuses.get("suspected", 0),
                    "not_triggered": statuses.get("not_triggered", 0),
                    "error": statuses.get("error", 0),
                },
                "final_assessment": verdict["value"],
                "final_assessment_label": verdict["label"],
                "final_assessment_reason": verdict["reason"],
                "plan_analysis": _build_runtime_plan_analysis(rounds, results, source),
                "results": results,
            }
        )

    return sorted(reports, key=lambda current: int(current["created_at_ts"]), reverse=True)


def _build_runtime_rounds(results: list[dict[str, object]]) -> list[dict[str, object]]:
    rounds_map: dict[int, dict[str, object]] = {}
    for item in results:
        round_index = int(item.get("round_index") or 0)
        bucket = rounds_map.setdefault(
            round_index,
            {
                "round_index": round_index,
                "round_label": item.get("round_label") or (f"第 {round_index} 轮" if round_index else "未命名轮次"),
                "vector": item.get("vector"),
                "payload": item.get("payload"),
                "candidate_id": item.get("candidate_id"),
                "round_reason": item.get("round_reason"),
                "result_count": 0,
                "confirmed_count": 0,
                "suspected_count": 0,
                "not_triggered_count": 0,
            },
        )
        bucket["result_count"] += 1
        if item.get("level") == "confirmed":
            bucket["confirmed_count"] += 1
        elif item.get("level") == "suspected":
            bucket["suspected_count"] += 1
        elif item.get("level") == "not_triggered":
            bucket["not_triggered_count"] += 1
    return sorted(rounds_map.values(), key=lambda current: int(current["round_index"]))


def _build_runtime_plan_analysis(
    rounds: list[dict[str, object]],
    results: list[dict[str, object]],
    source: str,
) -> dict[str, object] | None:
    if source != "ai_multi_round" or not rounds:
        return None

    strongest_result = next((item for item in results if item.get("level") == "confirmed"), None)
    if strongest_result is None:
        strongest_result = next((item for item in results if item.get("level") == "suspected"), None)
    if strongest_result is None and results:
        strongest_result = results[0]

    best_round = max(
        rounds,
        key=lambda item: (
            int(item.get("confirmed_count") or 0),
            int(item.get("suspected_count") or 0),
            -int(item.get("not_triggered_count") or 0),
            -int(item.get("round_index") or 0),
        ),
    )

    expectations: list[dict[str, object]] = []
    for item in rounds:
        confirmed_count = int(item.get("confirmed_count") or 0)
        suspected_count = int(item.get("suspected_count") or 0)
        not_triggered_count = int(item.get("not_triggered_count") or 0)
        if confirmed_count > 0:
            status = "matched"
            status_label = "达到预期"
            reason = f"这一轮已经出现 {confirmed_count} 条已确认结果，说明推荐顺序与当前页面输入面基本匹配。"
        elif suspected_count > 0:
            status = "partial"
            status_label = "部分达到预期"
            reason = f"这一轮虽然没有稳定确认，但已经出现 {suspected_count} 条可疑信号，仍值得继续人工复核。"
        else:
            status = "weak"
            status_label = "低于预期"
            reason = f"这一轮主要表现为未触发，共 {not_triggered_count} 条结果，说明当前探针与页面上下文匹配度较弱。"
        expectations.append(
            {
                "round_index": item.get("round_index"),
                "round_label": item.get("round_label"),
                "vector": item.get("vector"),
                "status": status,
                "status_label": status_label,
                "confirmed_count": confirmed_count,
                "suspected_count": suspected_count,
                "not_triggered_count": not_triggered_count,
                "reason": reason,
            }
        )

    strongest_signal_label = "未观察到稳定信号"
    strongest_signal_reason = "当前多轮验证没有产生稳定的已确认回显，仍需要结合源码与页面行为继续判断。"
    key_parameter = None
    if strongest_result is not None:
        key_parameter = strongest_result.get("parameter_name")
        if strongest_result.get("level") == "confirmed":
            strongest_signal_label = "已确认回显"
            strongest_signal_reason = (
                f"{strongest_result.get('round_label') or '某一轮'} 在参数 "
                f"{strongest_result.get('parameter_name') or '-'} 上出现了稳定回显，"
                f"上下文为 {strongest_result.get('reflection_context_label') or '未知'}。"
            )
        elif strongest_result.get("level") == "suspected":
            strongest_signal_label = "可疑信号"
            strongest_signal_reason = (
                f"{strongest_result.get('round_label') or '某一轮'} 在参数 "
                f"{strongest_result.get('parameter_name') or '-'} 上出现了可疑信号，"
                "但还没有形成稳定确认结果。"
            )

    return {
        "best_round_label": best_round.get("round_label"),
        "best_vector": best_round.get("vector"),
        "key_parameter": key_parameter,
        "strongest_signal_label": strongest_signal_label,
        "strongest_signal_reason": strongest_signal_reason,
        "expectations": expectations,
    }


def _summarize_runtime_report(
    statuses: Counter,
    results: list[dict[str, object]],
    source: str,
) -> dict[str, str]:
    confirmed = int(statuses.get("confirmed", 0))
    suspected = int(statuses.get("suspected", 0))
    not_triggered = int(statuses.get("not_triggered", 0))
    if confirmed:
        contexts = sorted({str(item.get("reflection_context_label") or "") for item in results if item.get("reflection_context_label")})
        context_text = f"，主要出现在 {', '.join(contexts[:3])}" if contexts else ""
        if source == "ai_multi_round":
            return {
                "value": "confirmed",
                "label": "多轮验证已确认",
                "reason": f"多轮验证中至少有 {confirmed} 条结果出现稳定回显或明确触发信号{context_text}，说明当前页面存在较强的输入进入输出链路。",
            }
        return {
            "value": "confirmed",
            "label": "验证已确认",
            "reason": f"当前报告中至少有 {confirmed} 条结果出现稳定回显或明确触发信号{context_text}。",
        }
    if suspected:
        return {
            "value": "suspected",
            "label": "仍需人工复核",
            "reason": f"当前报告有 {suspected} 条结果出现可疑信号，但还没有稳定的已确认回显，建议继续结合源码和页面行为复核。",
        }
    if not_triggered and not confirmed and not suspected:
        return {
            "value": "not_triggered",
            "label": "当前未触发",
            "reason": f"本次报告共有 {not_triggered} 条结果未触发明显回显，说明当前探针组合暂未观察到稳定信号，但不代表页面一定安全。",
        }
    return {
        "value": "unknown",
        "label": "结果不足",
        "reason": "当前报告缺少足够结果，暂时无法形成稳定结论。",
    }


def _select_manual_retest_report(reports: list[dict[str, object]], batch_id: str | None) -> dict[str, object] | None:
    return _select_runtime_report(reports, batch_id)


def _select_runtime_report(reports: list[dict[str, object]], batch_id: str | None) -> dict[str, object] | None:
    if not reports:
        return None
    if batch_id:
        for item in reports:
            if str(item.get("batch_id")) == batch_id:
                return item
    return reports[0]


def _recommend_ai_multi_round_plan(
    page_context: dict[str, object],
    candidates: list[dict[str, str]],
    mode: str,
) -> dict[str, object]:
    analyzer = get_analyzer()
    result = analyzer.recommend_validation_plan(page_context, candidates, mode)
    if result.get("success"):
        try:
            raw = result["plan"]["content"]
            payload = json.loads(raw)
            selected: list[dict[str, str]] = []
            for item in payload.get("rounds") or []:
                candidate_id = str(item.get("candidate_id") or "").strip()
                candidate = next((c for c in candidates if c["id"] == candidate_id), None)
                if not candidate:
                    continue
                selected.append({**candidate, "reason": str(item.get("reason") or candidate.get("reason") or "")})
            if selected:
                limit = {"quick": 2, "standard": 3, "deep": 5}.get(mode, 3)
                return {
                    "provider": "ai",
                    "reason": str(payload.get("reason") or result["plan"]["summary"]),
                    "rounds": selected[:limit],
                }
        except Exception:
            pass

    limit = {"quick": 2, "standard": 3, "deep": 5}.get(mode, 3)
    return {
        "provider": "fallback",
        "reason": "根据页面输入面、风险线索和上下文类型，按最可能提高判断准确率的顺序执行安全探针验证。",
        "rounds": candidates[:limit],
    }


def _dynamic_level_sort_key(level: str) -> int:
    return {
        "confirmed": 0,
        "suspected": 1,
        "not_triggered": 2,
        "error": 3,
    }.get(level, 9)


def _reflection_context_label(context: str | None) -> str | None:
    return {
        "html_text": "HTML 文本",
        "html_attr": "HTML 属性",
        "script": "Script 上下文",
        "comment": "HTML 注释",
        "dom_hash": "Hash / DOM 读取",
        "unknown": "未知上下文",
    }.get(context or "")


def _explain_dynamic_verification(
    vector: str, status: str, parameter_name: str | None, evidence: str | None
) -> dict[str, str]:
    parameter_label = parameter_name or "未命名参数"
    if status == "verified":
        return {
            "level": "confirmed",
            "summary": f"动态验证已确认 {vector} 向量可触发，参数 {parameter_label} 的 payload 在响应中出现。",
            "risk": "这说明目标页面存在真实的输入回显链路，若缺少输出编码或上下文隔离，通常可进一步演化为真实 XSS。",
            "recommendation": "优先修复该参数的输出编码与上下文处理逻辑，并核查是否可在 HTML、属性或脚本上下文中执行。",
        }
    if status == "suspected":
        return {
            "level": "suspected",
            "summary": f"动态验证发现 {vector} 向量存在明显信号，但当前仍需进一步人工确认。",
            "risk": "页面脚本已读取相关输入源，这通常意味着存在可被利用的前提条件。",
            "recommendation": "建议结合 Selenium 或浏览器开发者工具继续确认 DOM 变化和脚本执行路径。",
        }
    if status == "error":
        return {
            "level": "error",
            "summary": f"动态验证在请求 {vector} 向量时出错，未能完成有效验证。",
            "risk": "当前结果不能说明目标安全，只表示本次验证链路失败。",
            "recommendation": "优先检查网络、代理、TLS 或目标站点限制，再重新执行动态验证。",
        }
    return {
        "level": "not_triggered",
        "summary": f"动态验证未观察到 {vector} 向量对参数 {parameter_label} 产生明显回显。",
        "risk": "这只能说明当前 payload 未触发，不代表目标不存在变种利用路径。",
        "recommendation": "可以尝试更贴合页面上下文的 payload，或结合静态结果继续人工复核。",
    }


def _to_beijing_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TZ)
    return value.astimezone(BEIJING_TZ)


def _to_beijing_iso(value: datetime | None) -> str | None:
    dt = _to_beijing_dt(value)
    return dt.isoformat() if dt else None


def _to_beijing_ts(value: datetime | None) -> int | None:
    dt = _to_beijing_dt(value)
    return int(dt.timestamp()) if dt else None


if __name__ == "__main__":
    from run_dev import main

    main()
