from __future__ import annotations

import html
import json
from datetime import datetime


def build_export_filename(job_id: str, export_format: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "html" if export_format == "html" else "json"
    return f"xss_report_{job_id}_{stamp}.{suffix}"


def render_report_json(report_data: dict[str, object]) -> str:
    return json.dumps(report_data, ensure_ascii=False, indent=2)


def render_report_html(report_data: dict[str, object]) -> str:
    job = report_data.get("job") or {}
    stats = report_data.get("stats") or {}
    summary = report_data.get("summary") or {}
    findings = report_data.get("findings") or []
    verifications = ((report_data.get("dynamic_verification") or {}).get("results")) or []
    ai_reports = report_data.get("ai_reports") or []

    findings_html = "".join(_render_finding_card(item) for item in findings)
    verifications_html = "".join(_render_verification_card(item) for item in verifications)
    ai_reports_html = "".join(_render_ai_card(item) for item in ai_reports)
    risk_pages_html = "".join(
        f"<tr><td>{html.escape(str(item.get('url') or '-'))}</td>"
        f"<td>{html.escape(str(item.get('findings') or 0))}</td>"
        f"<td>{html.escape(str(item.get('highest_severity') or '-'))}</td></tr>"
        for item in (summary.get("top_risk_pages") or [])
    )

    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>XSS 扫描报告</title>
    <style>
      body {{ font-family: "Microsoft YaHei", sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
      .wrap {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
      .hero, .card {{ background: #fff; border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 18px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06); }}
      .hero {{ padding: 24px; margin-bottom: 18px; }}
      .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }}
      .metric {{ padding: 16px; background: linear-gradient(180deg, #eef2ff, #ffffff); border-radius: 14px; }}
      .metric-label {{ font-size: 13px; color: #475569; }}
      .metric-value {{ margin-top: 8px; font-size: 24px; font-weight: 800; }}
      .section {{ margin-top: 18px; }}
      .section-title {{ font-size: 20px; font-weight: 800; margin: 0 0 12px; }}
      .card {{ padding: 18px; margin-bottom: 14px; }}
      .meta {{ color: #475569; font-size: 14px; }}
      .pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px; font-weight: 700; margin-right: 8px; }}
      .danger {{ background: #fee2e2; color: #b91c1c; }}
      .warn {{ background: #fef3c7; color: #b45309; }}
      .safe {{ background: #dcfce7; color: #166534; }}
      table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 14px; overflow: hidden; }}
      th, td {{ padding: 12px 14px; border-bottom: 1px solid rgba(15, 23, 42, 0.08); text-align: left; vertical-align: top; }}
      th {{ background: #f8fafc; font-size: 13px; color: #475569; }}
      code {{ background: #f8fafc; padding: 2px 6px; border-radius: 6px; }}
      pre {{ background: #0f172a; color: #e2e8f0; padding: 14px; border-radius: 12px; overflow-x: auto; white-space: pre-wrap; }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <section class="hero">
        <h1 style="margin:0 0 8px;">XSS 扫描导出报告</h1>
        <div class="meta">任务地址：{html.escape(str(job.get("target_url") or "-"))}</div>
        <div class="meta">任务状态：{html.escape(str(job.get("status") or "-"))}</div>
        <div class="meta">导出时间：{html.escape(str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))}</div>
        <div class="grid">
          <div class="metric"><div class="metric-label">页面数</div><div class="metric-value">{html.escape(str(stats.get("pages") or 0))}</div></div>
          <div class="metric"><div class="metric-label">漏洞族</div><div class="metric-value">{html.escape(str(stats.get("findings") or 0))}</div></div>
          <div class="metric"><div class="metric-label">命中实例</div><div class="metric-value">{html.escape(str(stats.get("instances") or 0))}</div></div>
          <div class="metric"><div class="metric-label">动态验证结果</div><div class="metric-value">{html.escape(str(len(verifications)))}</div></div>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">高风险页面</h2>
        <div class="card">
          <table>
            <thead><tr><th>URL</th><th>漏洞数</th><th>最高等级</th></tr></thead>
            <tbody>{risk_pages_html or '<tr><td colspan="3">无</td></tr>'}</tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">发现列表</h2>
        {findings_html or '<div class="card">无发现</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">动态验证结果</h2>
        {verifications_html or '<div class="card">无动态验证结果</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">AI 分析摘要</h2>
        {ai_reports_html or '<div class="card">无 AI 报告</div>'}
      </section>
    </div>
  </body>
</html>"""


def _render_finding_card(item: dict[str, object]) -> str:
    instances = item.get("instances") or []
    instance_lines = "".join(
        f"<li>第 {html.escape(str(instance.get('line') or '-'))} 行："
        f"<code>{html.escape(str(instance.get('snippet') or '-'))}</code></li>"
        for instance in instances[:8]
    )
    return (
        '<div class="card">'
        f'<div><span class="pill {_severity_pill_class(str(item.get("severity") or ""))}">{html.escape(str(item.get("severity_label") or item.get("severity") or "-"))}</span>'
        f'<strong>{html.escape(str(item.get("title") or "-"))}</strong></div>'
        f'<div class="meta" style="margin-top:8px;">类型：{html.escape(str(item.get("kind_display") or item.get("kind") or "-"))}</div>'
        f'<div class="meta">最终判断：{html.escape(str(item.get("final_assessment_label") or item.get("final_assessment") or "-"))}</div>'
        f'<div class="meta">人工状态：{html.escape(str(item.get("review_status_label") or "-"))}</div>'
        f'<div class="meta">摘要：{html.escape(str(item.get("summary") or "-"))}</div>'
        f'<div class="meta">风险说明：{html.escape(str(item.get("reason") or "-"))}</div>'
        f'<div class="meta">修复建议：{html.escape(str(item.get("recommendation") or "-"))}</div>'
        f'<ul>{instance_lines or "<li>无实例详情</li>"}</ul>'
        '</div>'
    )


def _render_verification_card(item: dict[str, object]) -> str:
    return (
        '<div class="card">'
        f'<div><span class="pill {_verification_pill_class(str(item.get("level") or ""))}">{html.escape(str(item.get("level_label") or "-"))}</span>'
        f'<strong>{html.escape(str(item.get("target_url") or "-"))}</strong></div>'
        f'<div class="meta" style="margin-top:8px;">向量：{html.escape(str(item.get("vector") or "-"))} / 参数：{html.escape(str(item.get("parameter_name") or "-"))}</div>'
        f'<div class="meta">结论：{html.escape(str(item.get("summary") or "-"))}</div>'
        f'<div class="meta">说明：{html.escape(str(item.get("reason") or "-"))}</div>'
        f'<div class="meta">建议：{html.escape(str(item.get("recommendation") or "-"))}</div>'
        f'<pre>{html.escape(str(item.get("evidence") or "-"))}</pre>'
        '</div>'
    )


def _render_ai_card(item: dict[str, object]) -> str:
    return (
        '<div class="card">'
        f'<div><strong>{html.escape(str(item.get("page_url") or "-"))}</strong></div>'
        f'<div class="meta" style="margin-top:8px;">时间：{html.escape(str(item.get("created_at") or "-"))}</div>'
        f'<div class="meta">摘要：{html.escape(str(item.get("summary") or "-"))}</div>'
        f'<div class="meta">风险评估：{html.escape(str(item.get("risk_assessment") or "-"))}</div>'
        '</div>'
    )


def _severity_pill_class(severity: str) -> str:
    mapping = {"high": "danger", "medium": "warn", "low": "safe"}
    return mapping.get(severity, "")


def _verification_pill_class(level: str) -> str:
    mapping = {"confirmed": "danger", "suspected": "warn", "not_triggered": "safe"}
    return mapping.get(level, "")
