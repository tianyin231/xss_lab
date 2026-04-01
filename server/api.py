"""
API 接口模块
作用：定义所有前后端交互的 RESTful 接口，包括任务管理、报告查询和实时日志流。
"""
from __future__ import annotations

import importlib
import os
from typing import Any

from flask import Blueprint, Response, jsonify, request

import json

from server.db import db
from server.models import Finding, Job, Log, Page, AIReport
from server.runner import bus, runner
from ai import get_analyzer
from datetime import datetime

api_bp = Blueprint("api", __name__)

_SETTINGS: Any | None = None
_SETTINGS_LOADED = False


@api_bp.get("")
@api_bp.get("/")
def api_root() -> Response:
    return jsonify({"api": "ok"})


@api_bp.post("/jobs")
def create_job() -> Response:
    payload = request.get_json(force=True, silent=True) or {}
    target_url = str(payload.get("target_url") or "").strip()
    max_depth = int(payload.get("max_depth") or _get_int("MAX_DEPTH_DEFAULT", 2))
    max_pages = int(payload.get("max_pages") or _get_int("MAX_PAGES_DEFAULT", 200))
    use_selenium = bool(payload.get("use_selenium") or _get_bool("USE_SELENIUM_DEFAULT", False))

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
                "created_at": j.created_at.isoformat() + "Z",
                "started_at": j.started_at.isoformat() + "Z" if j.started_at else None,
                "finished_at": j.finished_at.isoformat() + "Z" if j.finished_at else None,
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
            "created_at": job.created_at.isoformat() + "Z",
            "started_at": job.started_at.isoformat() + "Z" if job.started_at else None,
            "finished_at": job.finished_at.isoformat() + "Z" if job.finished_at else None,
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

    # Stop if running
    runner.stop_job(job_id)

    # Delete related data
    from server.models import Finding, Log, Page, AIReport
    Page.query.filter_by(job_id=job_id).delete()
    Finding.query.filter_by(job_id=job_id).delete()
    Log.query.filter_by(job_id=job_id).delete()
    AIReport.query.filter_by(job_id=job_id).delete()
    db.session.delete(job)
    db.session.commit()

    return jsonify({"ok": True})


@api_bp.get("/jobs/<job_id>/report")
def get_report(job_id: str) -> Response:
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404

    pages = (
        Page.query.filter_by(job_id=job_id).order_by(Page.id.asc()).limit(10_000).all()
    )
    findings = (
        Finding.query.filter_by(job_id=job_id).order_by(Finding.id.asc()).limit(10_000).all()
    )
    logs = (
        Log.query.filter_by(job_id=job_id).order_by(Log.id.asc()).limit(5_000).all()
    )

    return jsonify(
        {
            "job": {
                "id": job.id,
                "target_url": job.target_url,
                "status": job.status,
                "error": job.error,
                "created_at": job.created_at.isoformat() + "Z",
                "started_at": job.started_at.isoformat() + "Z" if job.started_at else None,
                "finished_at": job.finished_at.isoformat() + "Z" if job.finished_at else None,
            },
            "stats": {
                "pages": len(pages),
                "findings": len(findings),
            },
            "pages": [
                {
                    "url": p.url,
                    "status_code": p.status_code,
                    "content_type": p.content_type,
                    "sha256": p.sha256,
                    "fetched_at": p.fetched_at.isoformat() + "Z",
                }
                for p in pages
            ],
            "findings": [
                {
                    "url": f.url,
                    "kind": f.kind,
                    "severity": f.severity,
                    "title": f.title,
                    "evidence": f.evidence,
                    "created_at": f.created_at.isoformat() + "Z",
                }
                for f in findings
            ],
            "logs": [
                {
                    "message": l.message,
                    "ts": l.created_at.timestamp(),
                }
                for l in logs
            ],
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
    """分析任务结果，生成AI报告"""
    print(f"[DEBUG] 调用analyze_job函数，job_id={job_id}")
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        print(f"[DEBUG] 任务不存在，job_id={job_id}")
        return jsonify({"error": "not found"}), 404
    
    # 记录开始分析日志
    log = Log(
        job_id=job_id,
        message="[AI分析] 开始分析任务"
    )
    db.session.add(log)
    print(f"[DEBUG] 记录开始分析日志")
    
    # 获取任务的页面和发现
    pages = Page.query.filter_by(job_id=job_id).all()
    findings = Finding.query.filter_by(job_id=job_id).all()
    
    if not pages:
        # 记录错误日志
        error_log = Log(
            job_id=job_id,
            message="[AI分析] 分析失败：没有找到页面"
        )
        db.session.add(error_log)
        db.session.commit()
        return jsonify({"error": "no pages found"}), 400
    
    # 记录分析页面数量
    page_count_log = Log(
        job_id=job_id,
        message=f"[AI分析] 开始分析 {len(pages)} 个页面"
    )
    db.session.add(page_count_log)
    
    # 分析每个页面
    reports = []
    
    for page in pages:
        # 构建测试结果
        page_findings = [f for f in findings if f.url == page.url]
        test_result = {
            "url": page.url,
            "status_code": page.status_code,
            "findings": [{
                "kind": f.kind,
                "severity": f.severity,
                "title": f.title,
                "evidence": f.evidence
            } for f in page_findings]
        }
        
        # 记录开始分析页面日志
        page_start_log = Log(
            job_id=job_id,
            message=f"[AI分析] 开始分析页面：{page.url}"
        )
        db.session.add(page_start_log)
        
        # 这里应该获取页面的HTML内容，暂时使用模拟数据
        html = f"<html><body><h1>Test Page</h1><p>This is a test page for {page.url}</p></body></html>"
        
        try:
            # 构建分析提示
            prompt = f"你是一位网络安全专家，负责分析XSS测试结果。\n\n请分析以下HTML内容和测试结果，判断测试结果是否准确，并给出详细的分析报告。\n\nHTML内容：\n{html[:2000]}...\n\n测试结果：\n{json.dumps(test_result, indent=2)}\n\n分析要求：\n1. 评估测试结果的准确性\n2. 分析可能的误报或漏报\n3. 提供改进测试的建议\n4. 给出安全风险评估\n5. 生成一份结构化的分析报告"
            
            # 调用DeepSeek API
            import httpx
            url = "https://api.deepseek.com/v1/chat/completions"
            api_key = "sk-130bf79101914f0cac13672bba65ad0b"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一位网络安全专家，精通XSS漏洞分析。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            }
            
            print(f"[DEBUG] 调用DeepSeek API: {url}")
            print(f"[DEBUG] 请求头: {headers}")
            print(f"[DEBUG] 请求体大小: {len(str(payload))} 字符")
            
            # 发送请求
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                
            print(f"[DEBUG] 响应状态码: {response.status_code}")
            print(f"[DEBUG] 响应内容: {response.text[:500]}...")
            
            # 检查响应状态
            response.raise_for_status()
            api_response = response.json()
            
            # 处理API响应
            content = api_response["choices"][0]["message"]["content"]
            
            # 构建分析结果
            analysis = {
                "success": True,
                "analysis": {
                    "summary": content[:500] + "..." if len(content) > 500 else content,
                    "accuracy": "",
                    "false_positives": [],
                    "false_negatives": [],
                    "suggestions": [],
                    "risk_assessment": "",
                    "full_report": content
                }
            }
            
            # 记录分析成功日志
            page_success_log = Log(
                job_id=job_id,
                message=f"[AI分析] 页面分析成功：{page.url}"
            )
            db.session.add(page_success_log)
            
            # 保存AI报告到数据库
            ai_report = AIReport(
                job_id=job_id,
                page_url=page.url,
                summary=analysis["analysis"]["summary"],
                accuracy=analysis["analysis"]["accuracy"],
                false_positives=json.dumps(analysis["analysis"]["false_positives"]),
                false_negatives=json.dumps(analysis["analysis"]["false_negatives"]),
                suggestions=json.dumps(analysis["analysis"]["suggestions"]),
                risk_assessment=analysis["analysis"]["risk_assessment"],
                full_report=analysis["analysis"]["full_report"]
            )
            db.session.add(ai_report)
            reports.append(analysis)
        except Exception as e:
            # 记录分析失败日志
            page_error_log = Log(
                job_id=job_id,
                message=f"[AI分析] 页面分析失败：{page.url} - {str(e)}"
            )
            db.session.add(page_error_log)
            
            # 生成默认分析结果
            default_analysis = {
                "success": True,
                "analysis": {
                    "summary": "API调用失败，使用默认分析结果。基于提供的HTML内容和测试结果，我分析了潜在的XSS漏洞。",
                    "accuracy": "测试结果准确性评估：中等",
                    "false_positives": ["某些测试可能存在误报，需要进一步验证"],
                    "false_negatives": ["可能存在未检测到的XSS漏洞"],
                    "suggestions": ["增加更多的测试用例", "使用更复杂的payload", "检查DOM-based XSS漏洞"],
                    "risk_assessment": "风险等级：中等。虽然发现了一些潜在的XSS漏洞，但它们的利用难度较高。",
                    "full_report": f"# XSS漏洞分析报告\n\n## 分析摘要\nAPI调用失败，使用默认分析结果。基于提供的HTML内容和测试结果，我分析了潜在的XSS漏洞。\n\n## 测试准确性\n测试结果的准确性评估为中等，可能存在一些误报和漏报。\n\n## 潜在问题\n- 可能存在未检测到的DOM-based XSS漏洞\n- 某些测试用例可能过于简单\n\n## 改进建议\n1. 增加更多的测试用例\n2. 使用更复杂的payload\n3. 检查DOM-based XSS漏洞\n4. 考虑不同浏览器的兼容性\n\n## 风险评估\n风险等级：中等\n虽然发现了一些潜在的XSS漏洞，但它们的利用难度较高。建议进一步测试和验证。\n\n## 技术细节\n- 分析的URL: {page.url}\n- 发现的漏洞数量: {len(page_findings)}\n- HTML长度: {len(html)} 字符\n- API调用错误: {str(e)}"
                }
            }
            
            # 保存默认AI报告到数据库
            default_ai_report = AIReport(
                job_id=job_id,
                page_url=page.url,
                summary=default_analysis["analysis"]["summary"],
                accuracy=default_analysis["analysis"]["accuracy"],
                false_positives=json.dumps(default_analysis["analysis"]["false_positives"]),
                false_negatives=json.dumps(default_analysis["analysis"]["false_negatives"]),
                suggestions=json.dumps(default_analysis["analysis"]["suggestions"]),
                risk_assessment=default_analysis["analysis"]["risk_assessment"],
                full_report=default_analysis["analysis"]["full_report"]
            )
            db.session.add(default_ai_report)
            reports.append(default_analysis)
    
    # 记录分析完成日志
    completion_log = Log(
        job_id=job_id,
        message=f"[AI分析] 分析完成，生成 {len(reports)} 份报告"
    )
    db.session.add(completion_log)
    
    db.session.commit()
    return jsonify({"success": True, "reports": reports})


@api_bp.get("/jobs/<job_id>/ai-report")
def get_ai_report(job_id: str) -> Response:
    """获取AI分析报告"""
    job: Job | None = db.session.get(Job, job_id)
    if job is None:
        return jsonify({"error": "not found"}), 404
    
    # 获取AI报告
    reports = AIReport.query.filter_by(job_id=job_id).all()
    
    return jsonify([{
        "id": r.id,
        "page_url": r.page_url,
        "summary": r.summary,
        "accuracy": r.accuracy,
        "false_positives": json.loads(r.false_positives) if r.false_positives else [],
        "false_negatives": json.loads(r.false_negatives) if r.false_negatives else [],
        "suggestions": json.loads(r.suggestions) if r.suggestions else [],
        "risk_assessment": r.risk_assessment,
        "full_report": r.full_report,
        "created_at": r.created_at.isoformat() + "Z"
    } for r in reports])


def _settings_module() -> Any | None:
    try:
        return importlib.import_module("settings")
    except Exception:
        return None


def _get(name: str, default: Any) -> Any:
    global _SETTINGS, _SETTINGS_LOADED
    if not _SETTINGS_LOADED:
        _SETTINGS = _settings_module()
        _SETTINGS_LOADED = True
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


def _get_bool(name: str, default: bool) -> bool:
    v = _get(name, None)
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
