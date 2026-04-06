"""HTTP API 路由。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from ai import get_analyzer
from app_config import get_bool, get_int
from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func

from server.db import db
from server.models import AIReport, DynamicVerification, Finding, FindingStatus, Job, Log, Page
from server.runner import bus, runner

api_bp = Blueprint("api", __name__)
BEIJING_TZ = timezone(timedelta(hours=8))


@api_bp.get("")
@api_bp.get("/")
def api_root() -> Response:
    return jsonify({"api": "ok"})


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
    )
    runner.start_job(job_id)
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

    pages_count = db.session.query(func.count(Page.id)).filter_by(job_id=job_id).scalar() or 0
    raw_findings = Finding.query.filter_by(job_id=job_id).order_by(Finding.id.asc()).all()
    logs = Log.query.filter_by(job_id=job_id).order_by(Log.id.desc()).limit(500).all()
    pages = Page.query.filter_by(job_id=job_id).order_by(Page.id.desc()).limit(100).all()
    verifications = DynamicVerification.query.filter_by(job_id=job_id).order_by(DynamicVerification.id.asc()).all()
    status_records = FindingStatus.query.filter_by(job_id=job_id).all()

    grouped_findings = _build_grouped_findings(raw_findings, verifications, status_records)
    severity_stats = Counter(item["severity"] for item in grouped_findings)
    kind_stats = Counter(item["kind"] for item in grouped_findings)
    page_risk = _top_risk_pages(grouped_findings)
    verification_stats = Counter(item.status for item in verifications)

    pages.reverse()
    logs.reverse()

    return jsonify(
        {
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
                "by_kind": dict(kind_stats),
            },
            "summary": {
                "top_risk_pages": page_risk,
            },
            "dynamic_verification": {
                "enabled": get_bool("DYNAMIC_VERIFY_ENABLED", False),
                "stats": dict(verification_stats),
                "results": [
                    {
                        "id": item.id,
                        "page_id": item.page_id,
                        "page_url": item.page_url,
                        "target_url": item.target_url,
                        "vector": item.vector,
                        "parameter_name": item.parameter_name,
                        "payload": item.payload,
                        "status": item.status,
                        "evidence": _parse_dynamic_evidence(item.evidence)["detail"],
                        "engine": _parse_dynamic_evidence(item.evidence)["engine"],
                        "created_at": _to_beijing_iso(item.created_at),
                        **_explain_dynamic_verification(
                            item.vector,
                            item.status,
                            item.parameter_name,
                            _parse_dynamic_evidence(item.evidence)["detail"],
                        ),
                    }
                    for item in verifications
                ],
            },
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
    )


@api_bp.get("/jobs/<job_id>/events")
def job_events(job_id: str) -> Response:
    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(bus.stream(job_id), headers=headers)


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
        test_result = {
            "url": page.url,
            "status_code": page.status_code,
            "findings": [
                {
                    "kind": f.kind,
                    "severity": f.severity,
                    "title": f.title,
                    "evidence": f.evidence,
                }
                for f in page_findings
            ],
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


@api_bp.get("/jobs/<job_id>/ai-report")
def get_ai_report(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    reports = AIReport.query.filter_by(job_id=job_id).order_by(AIReport.id.asc()).all()
    return jsonify(
        [
            {
                "id": r.id,
                "page_url": r.page_url,
                "summary": r.summary,
                "accuracy": r.accuracy,
                "false_positives": json.loads(r.false_positives) if r.false_positives else [],
                "false_negatives": json.loads(r.false_negatives) if r.false_negatives else [],
                "suggestions": json.loads(r.suggestions) if r.suggestions else [],
                "risk_assessment": r.risk_assessment,
                "full_report": r.full_report,
                "created_at": _to_beijing_iso(r.created_at),
            }
            for r in reports
        ]
    )


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


def _group_findings(
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
        instances = sorted(group["instances"], key=lambda item: (item.get("line") or 0, item.get("snippet") or ""))
        urls = sorted(group["urls"])
        lines = [str(item["line"]) for item in instances if item.get("line")]
        summary = f"共命中 {len(instances)} 处，涉及 {len(urls)} 个页面"
        if lines:
            summary += f"，行号: {', '.join(lines[:8])}"
        grouped.append(
            {
                "url": urls[0] if urls else "",
                "urls": urls,
                "page_count": len(urls),
                "kind": group["kind"],
                "member_kinds": sorted(group["member_kinds"]),
                "severity": group["severity"],
                "title": group["title"],
                "summary": summary,
                "evidence": instances[0].get("snippet") or "",
                "instances": instances,
                "instance_count": len(instances),
                "reason": reason,
                "confidence": confidence,
                "recommendation": recommendation,
                "evidence_type": evidence_type,
                "created_at": group["created_at"],
            }
        )

    return sorted(grouped, key=lambda item: (_severity_score(item["severity"]), item["title"]), reverse=True)


def _parse_evidence(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return {
                "line": payload.get("line"),
                "label": payload.get("label"),
                "snippet": payload.get("snippet") or raw,
            }
    except Exception:
        pass
    return {"line": None, "label": None, "snippet": raw}


def _finding_family(kind: str, title: str, payload: dict[str, object]) -> tuple[str, str]:
    snippet = str(payload.get("snippet") or "").lower()

    if kind in {"inline_event_handler", "javascript_redirection"} and any(
        token in snippet for token in ("location.href", "window.location", "location.assign", "location.replace")
    ):
        return ("inline_event_navigation", "内联事件跳转风险")

    if kind in {"javascript_protocol", "data_protocol", "iframe_srcdoc"}:
        return ("executable_attribute", "可执行属性注入风险")

    return (kind, title)


def _explain_finding(kind: str, severity: str) -> tuple[str, str, str, str]:
    if kind == "inline_event_navigation":
        return (
            "页面通过内联事件直接触发跳转逻辑，这类写法常与 onclick 拼接脚本或路径混用，风险应整体审视。",
            "high",
            "建议把跳转逻辑移到 addEventListener 或受控函数中，避免在 HTML 属性里直接操作 location。",
            "html_attr",
        )
    if kind == "source_sink_flow":
        return (
            "页面中同时出现潜在输入源和危险输出点，存在较强的 DOM XSS 风险信号。",
            "high",
            "优先检查 URL、Cookie 等数据是否直接流入 innerHTML、document.write 等危险位置。",
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
        instances = sorted(group["instances"], key=lambda item: (item.get("line") or 0, item.get("snippet") or ""))
        urls = sorted(group["urls"])
        lines = [str(item["line"]) for item in instances if item.get("line")]
        summary = f"共命中 {len(instances)} 处，涉及 {len(urls)} 个页面"
        if lines:
            summary += f"，行号 {', '.join(lines[:8])}"
        status_record = status_map.get((str(group["kind"]), str(group["title"])))
        linked_verifications = _match_verifications(urls, verifications)
        verdict = _final_assessment(str(group["severity"]), linked_verifications)
        grouped.append(
            {
                "url": urls[0] if urls else "",
                "urls": urls,
                "page_count": len(urls),
                "kind": group["kind"],
                "member_kinds": sorted(group["member_kinds"]),
                "severity": group["severity"],
                "title": group["title"],
                "summary": summary,
                "evidence": instances[0].get("snippet") or "",
                "instances": instances,
                "instance_count": len(instances),
                "reason": reason,
                "confidence": confidence,
                "recommendation": recommendation,
                "evidence_type": evidence_type,
                "final_assessment": verdict["value"],
                "final_assessment_label": verdict["label"],
                "final_assessment_reason": verdict["reason"],
                "review_status": status_record.status if status_record else "open",
                "review_status_label": _review_status_label(status_record.status if status_record else "open"),
                "review_note": status_record.note if status_record else None,
                "matched_verifications": len(linked_verifications),
                "created_at": group["created_at"],
            }
        )

    return sorted(grouped, key=lambda item: (_severity_score(item["severity"]), item["title"]), reverse=True)


def _match_verifications(urls: list[str], verifications: list[DynamicVerification]) -> list[DynamicVerification]:
    url_set = {url for url in urls if url}
    return [item for item in verifications if item.page_url in url_set]


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


def _severity_score(severity: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(severity, 1)


def _parse_dynamic_evidence(raw: str | None) -> dict[str, str | None]:
    if not raw:
        return {"engine": None, "detail": None}
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return {
                "engine": payload.get("engine"),
                "detail": payload.get("detail") or raw,
            }
    except Exception:
        pass
    return {"engine": None, "detail": raw}


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
        return value.replace(tzinfo=BEIJING_TZ)
    return value.astimezone(BEIJING_TZ)


def _to_beijing_iso(value: datetime | None) -> str | None:
    dt = _to_beijing_dt(value)
    return dt.isoformat() if dt else None


def _to_beijing_ts(value: datetime | None) -> int | None:
    dt = _to_beijing_dt(value)
    return int(dt.timestamp()) if dt else None
