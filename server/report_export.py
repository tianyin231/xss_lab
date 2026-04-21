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
    page_workbenches = report_data.get("page_workbenches") or []
    manual_retest_reports = report_data.get("manual_retest_reports") or []
    ai_multi_round_reports = report_data.get("ai_multi_round_reports") or []

    findings_html = "".join(_render_finding_card(item) for item in findings)
    verifications_html = "".join(_render_verification_card(item) for item in verifications)
    ai_reports_html = "".join(_render_ai_card(item) for item in ai_reports)
    page_workbench_html = "".join(_render_page_workbench_card(item) for item in page_workbenches)
    manual_retest_html = "".join(_render_runtime_report_card(item, "手工复测报告") for item in manual_retest_reports)
    ai_multi_round_html = "".join(_render_runtime_report_card(item, "AI 多轮验证报告") for item in ai_multi_round_reports)
    risk_pages_html = "".join(
        f"<tr><td>{_escape(item.get('url'))}</td>"
        f"<td>{_escape(item.get('findings') or 0)}</td>"
        f"<td>{_escape(item.get('highest_severity') or '-')}</td></tr>"
        for item in (summary.get("top_risk_pages") or [])
    )

    export_time = report_data.get("export_generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>XSS 扫描导出报告</title>
    <style>
      :root {{
        --bg: #f4f7fb;
        --card: rgba(255, 255, 255, 0.94);
        --line: rgba(15, 23, 42, 0.08);
        --text: #0f172a;
        --soft: #475569;
        --brand: #2563eb;
        --danger-bg: #fee2e2;
        --danger-text: #b91c1c;
        --warn-bg: #fef3c7;
        --warn-text: #b45309;
        --safe-bg: #dcfce7;
        --safe-text: #166534;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background:
          radial-gradient(circle at top left, rgba(37, 99, 235, 0.10), transparent 24%),
          linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
        color: var(--text);
        font: 14px/1.7 "Microsoft YaHei", "PingFang SC", sans-serif;
      }}
      .wrap {{ max-width: 1220px; margin: 0 auto; padding: 28px; }}
      .hero, .card, .table-card {{
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 22px;
        box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
      }}
      .hero {{ padding: 26px; margin-bottom: 18px; }}
      .eyebrow {{
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(37, 99, 235, 0.08);
        color: var(--brand);
        font-size: 12px;
        font-weight: 700;
      }}
      .hero h1 {{ margin: 12px 0 8px; font-size: 34px; line-height: 1.1; }}
      .meta {{ color: var(--soft); }}
      .meta-list {{ display: grid; gap: 4px; }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-top: 20px;
      }}
      .metric {{
        padding: 16px;
        border-radius: 18px;
        background: linear-gradient(180deg, #eef4ff 0%, #ffffff 100%);
      }}
      .metric-label {{ font-size: 13px; color: var(--soft); }}
      .metric-value {{ margin-top: 8px; font-size: 26px; font-weight: 800; }}
      .section {{ margin-top: 20px; }}
      .section-title {{ margin: 0 0 12px; font-size: 22px; font-weight: 800; }}
      .section-text {{ margin: 0 0 12px; color: var(--soft); }}
      .card {{ padding: 18px; margin-bottom: 14px; }}
      .table-card {{ overflow: hidden; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{
        padding: 12px 14px;
        border-bottom: 1px solid var(--line);
        text-align: left;
        vertical-align: top;
      }}
      th {{ background: #f8fafc; color: var(--soft); font-size: 13px; }}
      tr:last-child td {{ border-bottom: 0; }}
      .pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        background: rgba(37, 99, 235, 0.08);
        color: #1d4ed8;
      }}
      .danger {{ background: var(--danger-bg); color: var(--danger-text); }}
      .warn {{ background: var(--warn-bg); color: var(--warn-text); }}
      .safe {{ background: var(--safe-bg); color: var(--safe-text); }}
      .stack {{ display: grid; gap: 8px; }}
      .inline-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
      }}
      .tag {{
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.05);
        color: var(--soft);
        font-size: 12px;
      }}
      .title-row {{
        display: flex;
        justify-content: space-between;
        gap: 14px;
        align-items: flex-start;
        flex-wrap: wrap;
      }}
      .title-row strong {{ font-size: 18px; }}
      .cols-2 {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }}
      .subcard {{
        padding: 14px;
        border-radius: 16px;
        background: #f8fafc;
        border: 1px solid var(--line);
      }}
      .subcard-title {{ margin: 0 0 8px; font-size: 14px; font-weight: 800; }}
      ul {{ margin: 8px 0 0 18px; padding: 0; }}
      li + li {{ margin-top: 4px; }}
      pre {{
        margin: 8px 0 0;
        padding: 12px;
        border-radius: 14px;
        background: #0f172a;
        color: #e2e8f0;
        white-space: pre-wrap;
        overflow-x: auto;
      }}
      code {{
        font-family: Consolas, "SFMono-Regular", monospace;
        background: #f8fafc;
        border-radius: 8px;
        padding: 2px 6px;
      }}
      .empty {{
        padding: 22px;
        text-align: center;
        color: var(--soft);
      }}
      @media (max-width: 960px) {{
        .grid, .cols-2 {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <section class="hero">
        <div class="eyebrow">XSSLab Export</div>
        <h1>XSS 扫描导出报告</h1>
        <div class="meta-list">
          <div class="meta">目标地址：{_escape(job.get("target_url") or "-")}</div>
          <div class="meta">任务状态：{_escape(job.get("status") or "-")}</div>
          <div class="meta">导出时间：{_escape(export_time)}</div>
        </div>
        <div class="grid">
          <div class="metric"><div class="metric-label">页面数</div><div class="metric-value">{_escape(stats.get("pages") or 0)}</div></div>
          <div class="metric"><div class="metric-label">风险发现</div><div class="metric-value">{_escape(stats.get("findings") or 0)}</div></div>
          <div class="metric"><div class="metric-label">手工复测报告</div><div class="metric-value">{_escape(stats.get("manual_retest_reports") or 0)}</div></div>
          <div class="metric"><div class="metric-label">AI 多轮验证报告</div><div class="metric-value">{_escape(stats.get("ai_multi_round_reports") or 0)}</div></div>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">高风险页面</h2>
        <div class="table-card">
          <table>
            <thead><tr><th>URL</th><th>发现数</th><th>最高等级</th></tr></thead>
            <tbody>{risk_pages_html or '<tr><td colspan="3" class="empty">暂无高风险页面</td></tr>'}</tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">页面工作台摘要</h2>
        <p class="section-text">这里汇总了当前版本页面验证工作台里的核心能力，包括输入面画像、页面风险摘要、修复建议、手工复测和 AI 多轮验证摘要。</p>
        {page_workbench_html or '<div class="card empty">暂无页面工作台数据</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">风险发现列表</h2>
        {findings_html or '<div class="card empty">暂无风险发现</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">动态验证结果</h2>
        {verifications_html or '<div class="card empty">暂无动态验证结果</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">手工复测报告</h2>
        {manual_retest_html or '<div class="card empty">暂无手工复测报告</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">AI 多轮验证报告</h2>
        {ai_multi_round_html or '<div class="card empty">暂无 AI 多轮验证报告</div>'}
      </section>

      <section class="section">
        <h2 class="section-title">AI 分析摘要</h2>
        {ai_reports_html or '<div class="card empty">暂无 AI 分析结果</div>'}
      </section>
    </div>
  </body>
</html>"""


def _render_page_workbench_card(item: dict[str, object]) -> str:
    page = item.get("page") or {}
    input_profile = item.get("input_profile") or {}
    risk_summary = item.get("risk_summary") or {}
    related_findings = item.get("related_findings") or []
    repair_suggestions = item.get("repair_suggestions") or []
    latest_manual = item.get("latest_manual_retest_report")
    latest_ai = item.get("latest_ai_multi_round_report")
    query_tags = _render_tag_list(input_profile.get("query_params") or [])
    source_tags = _render_tag_list(input_profile.get("source_hints") or [])
    risk_tags = _render_tag_list(risk_summary.get("risky_api_hints") or [])
    query_html = query_tags or '<div class="meta">无显式 query 参数</div>'
    source_html = source_tags or '<div class="meta">无明显 source 线索</div>'
    risk_html = risk_tags or '<div class="meta">暂无明显风险线索</div>'
    repair_items = "".join(f"<li>{_escape(text)}</li>" for text in repair_suggestions)
    finding_items = "".join(
        f"<li>{_escape(entry.get('title') or '-')} <span class=\"meta\">({_escape(entry.get('severity_label') or '-')})</span></li>"
        for entry in related_findings[:6]
    )
    form_items = "".join(
        "<li>"
        f"{_escape((form.get('method') or 'get').upper())} {_escape(form.get('action') or page.get('url') or '-')}"
        f"{_render_tag_list(form.get('fields') or [])}"
        "</li>"
        for form in (input_profile.get("forms") or [])[:4]
    )
    return (
        '<article class="card">'
        '<div class="title-row">'
        f'<div class="stack"><strong>{_escape(page.get("url") or "-")}</strong>'
        f'<div class="meta">状态码：{_escape(page.get("status_code") or "-")} / 内容类型：{_escape(page.get("content_type") or "-")}</div>'
        f'<div class="meta">抓取时间：{_escape(page.get("fetched_at") or "-")}</div></div>'
        f'<span class="pill {_severity_pill_class(str(risk_summary.get("highest_severity") or ""))}">{_escape(risk_summary.get("highest_severity_label") or "-")}</span>'
        '</div>'
        '<div class="cols-2" style="margin-top:14px;">'
        '<div class="subcard">'
        '<div class="subcard-title">输入面画像</div>'
        f'<div class="meta">Query 参数</div>{query_html}'
        f'<div class="meta" style="margin-top:10px;">表单字段</div><ul>{form_items or "<li>未识别到表单字段</li>"}</ul>'
        f'<div class="meta" style="margin-top:10px;">Source 线索</div>{source_html}'
        f'<div class="inline-meta"><span class="tag">Hash 使用：{"是" if input_profile.get("uses_hash") else "否"}</span>'
        f'<span class="tag">内联事件：{_escape(input_profile.get("inline_event_count") or 0)}</span>'
        f'<span class="tag">脚本块：{_escape(input_profile.get("script_blocks") or 0)}</span></div>'
        '</div>'
        '<div class="subcard">'
        '<div class="subcard-title">风险摘要</div>'
        f'<div class="meta">关联发现：{_escape(risk_summary.get("total_findings") or 0)} / 动态结果：{_escape(risk_summary.get("dynamic_result_count") or 0)} / 已确认：{_escape(risk_summary.get("verified_result_count") or 0)}</div>'
        f'<div class="meta" style="margin-top:10px;">风险线索</div>{risk_html}'
        f'<div class="inline-meta"><span class="tag">DOM 汇点：{_escape(risk_summary.get("dom_sink_hits") or 0)}</span>'
        f'<span class="tag">内联事件：{_escape(risk_summary.get("inline_event_hits") or 0)}</span>'
        f'<span class="tag">动态验证：{"有" if risk_summary.get("has_dynamic_verification") else "无"}</span></div>'
        f'<div class="meta" style="margin-top:10px;">关联发现</div><ul>{finding_items or "<li>暂无关联发现</li>"}</ul>'
        '</div>'
        '</div>'
        '<div class="cols-2" style="margin-top:14px;">'
        '<div class="subcard">'
        '<div class="subcard-title">手工复测</div>'
        f'{_render_runtime_report_summary(latest_manual, "暂无手工复测报告")}'
        '</div>'
        '<div class="subcard">'
        '<div class="subcard-title">AI 多轮验证</div>'
        f'{_render_runtime_report_summary(latest_ai, "暂无 AI 多轮验证报告")}'
        '</div>'
        '</div>'
        '<div class="subcard" style="margin-top:14px;">'
        '<div class="subcard-title">修复建议</div>'
        f'<ul>{repair_items or "<li>暂无修复建议</li>"}</ul>'
        '</div>'
        '</article>'
    )


def _render_finding_card(item: dict[str, object]) -> str:
    instances = item.get("instances") or []
    verification_cards = "".join(
        f"<li>{_escape(result.get('level_label') or '-')} / {_escape(result.get('vector') or '-')} / {_escape(result.get('summary') or '-')}</li>"
        for result in (item.get("linked_verification_results") or [])[:4]
    )
    instance_lines = "".join(
        f"<li>第 {_escape(instance.get('line') or '-')} 行：<code>{_escape(instance.get('snippet') or '-')}</code></li>"
        for instance in instances[:8]
    )
    return (
        '<article class="card">'
        '<div class="title-row">'
        f'<div class="stack"><strong>{_escape(item.get("title") or "-")}</strong>'
        f'<div class="meta">{_escape(item.get("kind_display") or item.get("kind") or "-")}</div></div>'
        f'<span class="pill {_severity_pill_class(str(item.get("severity") or ""))}">{_escape(item.get("severity_label") or item.get("severity") or "-")}</span>'
        '</div>'
        f'<div class="meta" style="margin-top:10px;">最终判断：{_escape(item.get("final_assessment_label") or "-")} / 人工状态：{_escape(item.get("review_status_label") or "-")}</div>'
        f'<div class="meta">摘要：{_escape(item.get("summary") or "-")}</div>'
        f'<div class="meta">风险说明：{_escape(item.get("reason") or "-")}</div>'
        f'<div class="meta">修复建议：{_escape(item.get("recommendation") or "-")}</div>'
        '<div class="cols-2" style="margin-top:14px;">'
        f'<div class="subcard"><div class="subcard-title">命中实例</div><ul>{instance_lines or "<li>暂无实例</li>"}</ul></div>'
        f'<div class="subcard"><div class="subcard-title">关联动态验证</div><ul>{verification_cards or "<li>暂无关联动态验证</li>"}</ul></div>'
        '</div>'
        '</article>'
    )


def _render_verification_card(item: dict[str, object]) -> str:
    return (
        '<article class="card">'
        '<div class="title-row">'
        f'<div class="stack"><strong>{_escape(item.get("target_url") or "-")}</strong>'
        f'<div class="meta">{_escape(item.get("vector") or "-")} / {_escape(item.get("parameter_name") or "-")}</div></div>'
        f'<span class="pill {_verification_pill_class(str(item.get("level") or ""))}">{_escape(item.get("level_label") or "-")}</span>'
        '</div>'
        f'<div class="meta" style="margin-top:10px;">摘要：{_escape(item.get("summary") or "-")}</div>'
        f'<div class="meta">说明：{_escape(item.get("reason") or "-")}</div>'
        f'<div class="meta">建议：{_escape(item.get("recommendation") or "-")}</div>'
        f'<div class="inline-meta"><span class="tag">回显：{"已发现" if item.get("reflection_found") else "未发现"}</span>'
        f'<span class="tag">上下文：{_escape(item.get("reflection_context_label") or "-")}</span>'
        f'<span class="tag">时间：{_escape(item.get("created_at") or "-")}</span></div>'
        f'{_render_optional_pre("证据", item.get("evidence"))}'
        f'{_render_optional_pre("命中片段", item.get("reflection_snippet"))}'
        '</article>'
    )


def _render_ai_card(item: dict[str, object]) -> str:
    suggestions = item.get("suggestions") or []
    suggestion_items = "".join(f"<li>{_escape(text)}</li>" for text in suggestions[:6])
    return (
        '<article class="card">'
        f'<div><strong>{_escape(item.get("page_url") or "-")}</strong></div>'
        f'<div class="meta" style="margin-top:10px;">时间：{_escape(item.get("created_at") or "-")}</div>'
        f'<div class="meta">摘要：{_escape(item.get("summary") or "-")}</div>'
        f'<div class="meta">风险评估：{_escape(item.get("risk_assessment") or "-")}</div>'
        f'<ul>{suggestion_items or "<li>暂无建议</li>"}</ul>'
        '</article>'
    )


def _render_runtime_report_card(item: dict[str, object], title: str) -> str:
    rounds = item.get("rounds") or []
    results = item.get("results") or []
    expectations = ((item.get("plan_analysis") or {}).get("expectations")) or []
    target_url_items = "".join(f"<li>{_escape(url)}</li>" for url in (item.get("target_urls") or [])[:8])
    rounds_html = "".join(
        "<li>"
        f"{_escape(round_item.get('round_label') or '-')} / {_escape(round_item.get('vector') or '-')}"
        f" / 结果数：{_escape(round_item.get('result_count') or 0)} / 已确认：{_escape(round_item.get('confirmed_count') or 0)}"
        f"{' / 理由：' + _escape(round_item.get('round_reason')) if round_item.get('round_reason') else ''}"
        "</li>"
        for round_item in rounds
    )
    results_html = "".join(
        "<li>"
        f"{_escape(result.get('round_label') or title)} / {_escape(result.get('vector') or '-')} / {_escape(result.get('parameter_name') or '-')}"
        f" / {_escape(result.get('level_label') or '-')}"
        f"{' / ' + _escape(result.get('reflection_context_label')) if result.get('reflection_context_label') else ''}"
        "</li>"
        for result in results[:10]
    )
    expectation_html = "".join(
        "<li>"
        f"{_escape(entry.get('round_label') or '-')} / {_escape(entry.get('status_label') or '-')}"
        f" / {_escape(entry.get('reason') or '-')}"
        "</li>"
        for entry in expectations
    )
    plan_analysis = item.get("plan_analysis") or {}
    return (
        '<article class="card">'
        '<div class="title-row">'
        f'<div class="stack"><strong>{_escape(item.get("page_url") or "-")}</strong>'
        f'<div class="meta">{title} / {_escape(item.get("created_at") or "-")}</div></div>'
        f'<span class="pill {_verification_pill_class("confirmed" if item.get("verified_count") else "not_triggered")}">{_escape(item.get("final_assessment_label") or "-")}</span>'
        '</div>'
        f'<div class="meta" style="margin-top:10px;">模式：{_escape(item.get("mode") or "-")} / 计划来源：{_escape(item.get("plan_provider") or "-")}</div>'
        f'<div class="meta">结果数：{_escape(item.get("result_count") or 0)} / 已确认：{_escape(item.get("verified_count") or 0)} / 回显命中：{_escape(item.get("reflection_hits") or 0)}</div>'
        f'<div class="meta">理由：{_escape(item.get("reason") or "-")}</div>'
        f'<div class="meta">最终结论：{_escape(item.get("final_assessment_reason") or "-")}</div>'
        f'<div class="inline-meta">{_render_tag_list(item.get("vectors") or [])}{_render_tag_list(item.get("contexts") or [])}</div>'
        '<div class="cols-2" style="margin-top:14px;">'
        f'<div class="subcard"><div class="subcard-title">轮次计划</div><ul>{rounds_html or "<li>暂无轮次计划</li>"}</ul></div>'
        f'<div class="subcard"><div class="subcard-title">结果摘要</div><ul>{results_html or "<li>暂无结果</li>"}</ul></div>'
        '</div>'
        '<div class="cols-2" style="margin-top:14px;">'
        f'<div class="subcard"><div class="subcard-title">计划与实际</div>{_render_plan_analysis(plan_analysis)}<ul>{expectation_html or "<li>暂无计划偏差分析</li>"}</ul></div>'
        f'<div class="subcard"><div class="subcard-title">目标地址</div><ul>{target_url_items or "<li>暂无目标地址</li>"}</ul></div>'
        '</div>'
        '</article>'
    )


def _render_plan_analysis(plan_analysis: dict[str, object]) -> str:
    if not plan_analysis:
        return '<div class="meta">暂无计划分析</div>'
    parts = [
        f'<div class="meta">贡献最大轮次：{_escape(plan_analysis.get("best_round_label") or "-")}</div>',
        f'<div class="meta">最有效向量：{_escape(plan_analysis.get("best_vector") or "-")}</div>',
        f'<div class="meta">关键参数：{_escape(plan_analysis.get("key_parameter") or "-")}</div>',
        f'<div class="meta">最强信号：{_escape(plan_analysis.get("strongest_signal_label") or "-")}</div>',
    ]
    if plan_analysis.get("strongest_signal_reason"):
        parts.append(f'<div class="meta">{_escape(plan_analysis.get("strongest_signal_reason"))}</div>')
    return "".join(parts)


def _render_runtime_report_summary(report: dict[str, object] | None, empty_text: str) -> str:
    if not report:
        return f'<div class="meta">{_escape(empty_text)}</div>'
    return (
        f'<div class="meta">时间：{_escape(report.get("created_at") or "-")}</div>'
        f'<div class="meta">结果数：{_escape(report.get("result_count") or 0)} / 已确认：{_escape(report.get("verified_count") or 0)}</div>'
        f'<div class="meta">结论：{_escape(report.get("final_assessment_label") or "-")}</div>'
        f'<div class="meta">理由：{_escape(report.get("reason") or "-")}</div>'
    )


def _render_optional_pre(label: str, value: object) -> str:
    if value is None or value == "" or value == []:
        return ""
    return f'<div class="meta" style="margin-top:10px;">{_escape(label)}</div><pre>{_escape(value)}</pre>'


def _render_tag_list(values: list[object]) -> str:
    if not values:
        return ""
    return "".join(f'<span class="tag">{_escape(value)}</span>' for value in values if value not in {None, ""})


def _escape(value: object) -> str:
    return html.escape(str(value))


def _severity_pill_class(severity: str) -> str:
    mapping = {"high": "danger", "medium": "warn", "low": "safe"}
    return mapping.get(severity, "")


def _verification_pill_class(level: str) -> str:
    mapping = {"confirmed": "danger", "suspected": "warn", "not_triggered": "safe"}
    return mapping.get(level, "")
