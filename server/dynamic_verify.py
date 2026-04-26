"""轻量动态验证模块。"""
from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from lxml import html as lxml_html
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from app_config import get, get_bool, get_float, get_int
from server.db import db
from server.models import DynamicVerification, Finding, Job, Page


@dataclass(frozen=True)
class VerificationRecord:
    page_id: int | None
    page_url: str
    target_url: str
    vector: str
    engine: str
    parameter_name: str | None
    payload: str
    status: str
    evidence: str | None
    reflection_found: bool = False
    reflection_context: str | None = None
    reflection_snippet: str | None = None
    context_hint: str | None = None


def _safe_probe_preset(name: str) -> dict[str, str]:
    presets = get("DYNAMIC_VERIFY_SAFE_PROBE_PRESETS", {}) or {}
    item = presets.get(name) or {}
    return {
        "label": str(item.get("label") or name),
        "payload": str(item.get("payload") or ""),
        "vector": str(item.get("vector") or ""),
        "context": str(item.get("context") or ""),
        "reason": str(item.get("reason") or ""),
    }


def _suggested_payload_preset(name: str) -> dict[str, str]:
    presets = get("DYNAMIC_VERIFY_SUGGESTED_PAYLOAD_PRESETS", {}) or {}
    item = presets.get(name) or {}
    return {
        "label": str(item.get("label") or name),
        "payload": str(item.get("payload") or ""),
        "vector": str(item.get("vector") or ""),
    }


def _resolve_payload_alias(payload: str) -> str:
    safe_probe_aliases = {
        "xsslab_probe_text_2026": "query_text",
        'xsslab_probe_attr_2026"': "query_attr",
        "xsslab_probe_form_2026": "form_text",
        'xsslab_probe_form_attr_2026"': "form_attr",
        "xsslab_probe_hash_2026": "hash_text",
        "'xsslab_probe_js_2026'": "query_js",
        "'xsslab_probe_form_js_2026'": "form_js",
        "xsslab_probe_basic_2026": "query_fallback",
    }
    suggested_aliases = {
        "<img src=x onerror=alert(1)>": "html_tag",
        "<svg onload=alert(1)>": "svg_event",
        '" autofocus onfocus=alert(1) x="': "attr_breakout_double",
        "' onmouseover='alert(1)' x='": "attr_breakout_single",
        '" onmouseover="alert(1)': "query_attr_breakout",
        '";alert(1);//': "js_string_double",
        "';alert(1);//": "js_string_single",
        "javascript:alert(1)": "javascript_protocol",
        "xsslab_probe_2026": "basic_probe",
    }
    if payload in safe_probe_aliases:
        return _safe_probe_preset(safe_probe_aliases[payload])["payload"] or payload
    if payload in suggested_aliases:
        return _suggested_payload_preset(suggested_aliases[payload])["payload"] or payload
    return payload


def _default_dynamic_payload() -> str:
    return str(get("DYNAMIC_VERIFY_PAYLOAD", "Zxz_xss_payload"))


def _pick_preferred_payload(
    suggestions: list[dict[str, str]],
    preferred_vector: str = "",
    fallback: str | None = None,
) -> str:
    normalized_vector = str(preferred_vector or "").strip().lower()
    resolved_fallback = str(fallback or _default_dynamic_payload())

    if normalized_vector:
        for item in suggestions:
            if str(item.get("vector") or "").strip().lower() == normalized_vector:
                payload = str(item.get("payload") or "").strip()
                if payload:
                    return payload

    for item in suggestions:
        payload = str(item.get("payload") or "").strip()
        if payload:
            return payload

    return resolved_fallback


def run_dynamic_verification(job_id: str, log: Callable[[str], None] | None = None) -> int:
    if not get_bool("DYNAMIC_VERIFY_ENABLED", False):
        return 0

    job = Job.query.get(job_id)
    pages = (
        Page.query.filter_by(job_id=job_id)
        .filter(Page.content.isnot(None))
        .order_by(Page.id.asc())
        .limit(get_int("DYNAMIC_VERIFY_MAX_PAGES", 10))
        .all()
    )
    if not pages:
        _emit(log, "[动态验证] 未找到可验证页面")
        return 0

    findings = Finding.query.filter_by(job_id=job_id).all()
    findings_by_url: dict[str, list[Finding]] = {}
    for finding in findings:
        findings_by_url.setdefault(finding.url, []).append(finding)

    timeout = get_float("DYNAMIC_VERIFY_TIMEOUT", 15.0)
    wait_seconds = get_float("DYNAMIC_VERIFY_WAIT_SECONDS", 2.0)
    trust_env = get_bool("DYNAMIC_VERIFY_TRUST_ENV", False)
    ssl_verify = get_bool("DYNAMIC_VERIFY_SSL_VERIFY", False)
    use_selenium = get_bool("DYNAMIC_VERIFY_USE_SELENIUM", False) or bool(job.use_selenium if job else False)

    DynamicVerification.query.filter_by(job_id=job_id).delete()
    db.session.commit()

    engine_name = "selenium" if use_selenium else "http"
    _emit(log, f"[动态验证] 开始验证，共 {len(pages)} 个页面，使用 {engine_name} 引擎")
    records: list[VerificationRecord] = []
    driver = _init_driver(timeout) if use_selenium else None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=trust_env, verify=ssl_verify) as client:
            for page in pages:
                if not page.url.lower().startswith(("http://", "https://")):
                    continue
                page_findings = findings_by_url.get(page.url, [])
                vectors = _plan_verification_vectors(page, page_findings)
                suggested_payloads = suggest_payloads_for_page(page, page_findings)
                _emit(log, f"[动态验证] 页面 {page.url} 计划验证向量: {', '.join(vectors) if vectors else 'none'}")
                if "query" in vectors:
                    records.extend(
                        _verify_query(
                            client,
                            driver,
                            page,
                            _pick_preferred_payload(suggested_payloads, "query"),
                            wait_seconds,
                        )
                    )
                if "form" in vectors:
                    records.extend(
                        _verify_forms(
                            client,
                            driver,
                            page,
                            _pick_preferred_payload(suggested_payloads, "form"),
                            wait_seconds,
                        )
                    )
                if "hash" in vectors:
                    records.extend(
                        _verify_hash_runtime(
                            client,
                            driver,
                            page,
                            _pick_preferred_payload(suggested_payloads, "hash"),
                            wait_seconds,
                        )
                    )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    for record in records:
        db.session.add(
                DynamicVerification(
                    job_id=job_id,
                    page_id=record.page_id,
                page_url=record.page_url,
                target_url=record.target_url,
                vector=record.vector,
                    parameter_name=record.parameter_name,
                    payload=record.payload,
                    status=record.status,
                    evidence=_pack_evidence(
                        record.engine,
                        record.evidence,
                        reflection_found=record.reflection_found,
                        reflection_context=record.reflection_context,
                        reflection_snippet=record.reflection_snippet,
                        context_hint=record.context_hint,
                    ),
                )
            )
    db.session.commit()
    verified_count = sum(1 for item in records if item.status == "verified")
    _emit(log, f"[动态验证] 完成，共生成 {len(records)} 条结果，已触发 {verified_count} 条")
    return len(records)


def retest_finding(
    job_id: str,
    finding: Finding,
    payload: str | None = None,
    vector: str | None = None,
    use_selenium: bool | None = None,
) -> list[VerificationRecord]:
    page = Page.query.filter_by(job_id=job_id, url=finding.url).order_by(Page.id.desc()).first()
    if page is None:
        raise ValueError("page not found for finding")

    timeout = get_float("DYNAMIC_VERIFY_TIMEOUT", 15.0)
    wait_seconds = get_float("DYNAMIC_VERIFY_WAIT_SECONDS", 2.0)
    trust_env = get_bool("DYNAMIC_VERIFY_TRUST_ENV", False)
    ssl_verify = get_bool("DYNAMIC_VERIFY_SSL_VERIFY", False)
    job = db.session.get(Job, job_id)
    selenium_enabled = (
        use_selenium
        if use_selenium is not None
        else (get_bool("DYNAMIC_VERIFY_USE_SELENIUM", False) or bool(job.use_selenium if job else False))
    )

    planned_vectors = _plan_verification_vectors(page, [finding])
    if vector:
        normalized_vector = str(vector).strip().lower()
        if normalized_vector not in {"query", "form", "hash"}:
            raise ValueError("unsupported vector")
        planned_vectors = [item for item in planned_vectors if item == normalized_vector]
        if not planned_vectors:
            raise ValueError("requested vector is not applicable for this finding")

    if not planned_vectors:
        raise ValueError("no verification vector available for this finding")

    suggested_payloads = suggest_payloads_for_finding(finding)
    records: list[VerificationRecord] = []
    driver = _init_driver(timeout) if selenium_enabled else None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=trust_env, verify=ssl_verify) as client:
            for current_vector in planned_vectors:
                payload_text = str(payload or _pick_preferred_payload(suggested_payloads, current_vector))
                if current_vector == "query":
                    records.extend(_verify_query(client, driver, page, payload_text, wait_seconds))
                elif current_vector == "form":
                    records.extend(_verify_forms(client, driver, page, payload_text, wait_seconds))
                elif current_vector == "hash":
                    records.extend(_verify_hash_runtime(client, driver, page, payload_text, wait_seconds))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    return records


def retest_page(
    job_id: str,
    page: Page,
    payload: str | None = None,
    vector: str | None = None,
    use_selenium: bool | None = None,
) -> list[VerificationRecord]:
    timeout = get_float("DYNAMIC_VERIFY_TIMEOUT", 15.0)
    wait_seconds = get_float("DYNAMIC_VERIFY_WAIT_SECONDS", 2.0)
    trust_env = get_bool("DYNAMIC_VERIFY_TRUST_ENV", False)
    ssl_verify = get_bool("DYNAMIC_VERIFY_SSL_VERIFY", False)
    job = db.session.get(Job, job_id)
    selenium_enabled = (
        use_selenium
        if use_selenium is not None
        else (get_bool("DYNAMIC_VERIFY_USE_SELENIUM", False) or bool(job.use_selenium if job else False))
    )
    findings = Finding.query.filter_by(job_id=job_id, url=page.url).all()
    planned_vectors = _plan_verification_vectors(page, findings)
    if vector:
        normalized_vector = str(vector).strip().lower()
        if normalized_vector not in {"query", "form", "hash"}:
            raise ValueError("unsupported vector")
        planned_vectors = [item for item in planned_vectors if item == normalized_vector]
        if not planned_vectors:
            raise ValueError("requested vector is not applicable for this page")

    if not planned_vectors:
        raise ValueError("no verification vector available for this page")

    suggested_payloads = suggest_payloads_for_page(page, findings)
    records: list[VerificationRecord] = []
    driver = _init_driver(timeout) if selenium_enabled else None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=trust_env, verify=ssl_verify) as client:
            for current_vector in planned_vectors:
                payload_text = str(payload or _pick_preferred_payload(suggested_payloads, current_vector))
                if current_vector == "query":
                    records.extend(_verify_query(client, driver, page, payload_text, wait_seconds))
                elif current_vector == "form":
                    records.extend(_verify_forms(client, driver, page, payload_text, wait_seconds))
                elif current_vector == "hash":
                    records.extend(_verify_hash_runtime(client, driver, page, payload_text, wait_seconds))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    return records


def build_safe_probe_candidates_for_page(page: Page, findings: list[Finding], mode: str = "standard") -> list[dict[str, str]]:
    split_result = urlsplit(page.url)
    has_query = bool(parse_qsl(split_result.query, keep_blank_values=True))
    content = page.content or ""
    lower_content = content.lower()
    has_form = "<form" in lower_content
    has_hash = any(token in lower_content for token in ("location.hash", "hashchange", "decodeuricomponent(location.hash)"))

    candidates: list[dict[str, str]] = []

    def add(candidate_id: str, label: str, payload: str, vector: str, context: str, reason: str) -> None:
        item = {
            "id": candidate_id,
            "label": label,
            "payload": _resolve_payload_alias(payload),
            "vector": vector,
            "context": context,
            "reason": reason,
        }
        if item not in candidates:
            candidates.append(item)

    if has_query:
        add("query_text", "Query 文本探针", "xsslab_probe_text_2026", "query", "html_text", "优先确认查询参数是否进入页面文本内容。")
        add("query_attr", 'Query 属性探针', 'xsslab_probe_attr_2026"', "query", "html_attr", "用于观察属性边界附近是否出现探针。")

    if has_form:
        add("form_text", "Form 文本探针", "xsslab_probe_form_2026", "form", "html_text", "优先确认表单字段回显。")
        add("form_attr", 'Form 属性探针', 'xsslab_probe_form_attr_2026"', "form", "html_attr", "用于观察表单输入值是否进入属性位置。")

    if has_hash:
        add("hash_text", "Hash 文本探针", "xsslab_probe_hash_2026", "hash", "dom_hash", "用于确认 hash 片段是否被页面读取。")

    if any(item.kind in {"dom_sink", "source_sink_flow", "ast_data_flow"} for item in findings):
        add("query_js", "Query 脚本探针", "'xsslab_probe_js_2026'", "query", "script", "用于观察脚本字符串附近是否出现探针。")
        if has_form:
            add("form_js", "Form 脚本探针", "'xsslab_probe_form_js_2026'", "form", "script", "用于观察表单输入是否进入脚本上下文。")

    if not candidates:
        add("query_fallback", "基础探针", "xsslab_probe_basic_2026", "query", "summary", "没有明显输入面时，保留一个最基础的验证探针。")

    limit = {"quick": 2, "standard": 3, "deep": 5}.get(mode, 3)
    return candidates[:limit + 2]


def run_ai_multi_round_validation(
    job_id: str,
    page: Page,
    rounds: list[dict[str, str]],
    *,
    use_selenium: bool | None = None,
) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for index, round_item in enumerate(rounds, start=1):
        records = retest_page(
            job_id=job_id,
            page=page,
            payload=str(round_item.get("payload") or ""),
            vector=str(round_item.get("vector") or ""),
            use_selenium=use_selenium,
        )
        outputs.append(
            {
                "round_index": index,
                "round_label": str(round_item.get("label") or f"第 {index} 轮"),
                "candidate_id": str(round_item.get("id") or ""),
                "reason": str(round_item.get("reason") or ""),
                "vector": str(round_item.get("vector") or ""),
                "payload": str(round_item.get("payload") or ""),
                "context": str(round_item.get("context") or ""),
                "records": records,
            }
        )
    return outputs


def build_safe_probe_candidates_for_page_v2(page: Page, findings: list[Finding], mode: str = "standard") -> list[dict[str, str]]:
    split_result = urlsplit(page.url)
    has_query = bool(parse_qsl(split_result.query, keep_blank_values=True))
    content = page.content or ""
    lower_content = content.lower()
    has_form = "<form" in lower_content
    has_hash = any(token in lower_content for token in ("location.hash", "hashchange", "decodeuricomponent(location.hash)"))

    candidates: list[dict[str, str]] = []

    def add(candidate_id: str, label: str, payload: str, vector: str, context: str, reason: str) -> None:
        item = {
            "id": candidate_id,
            "label": label,
            "payload": _resolve_payload_alias(payload),
            "vector": vector,
            "context": context,
            "reason": reason,
        }
        if item not in candidates:
            candidates.append(item)

    if has_query:
        add("query_text", "Query 文本探针", "xsslab_probe_text_2026", "query", "html_text", "优先确认查询参数是否进入页面文本内容。")
        add("query_attr", "Query 属性探针", 'xsslab_probe_attr_2026"', "query", "html_attr", "用于观察属性边界附近是否出现探针。")

    if has_form:
        add("form_text", "Form 文本探针", "xsslab_probe_form_2026", "form", "html_text", "优先确认表单字段是否出现回显。")
        add("form_attr", "Form 属性探针", 'xsslab_probe_form_attr_2026"', "form", "html_attr", "用于观察表单输入值是否进入属性位置。")

    if has_hash:
        add("hash_text", "Hash 文本探针", "xsslab_probe_hash_2026", "hash", "dom_hash", "用于确认 hash 片段是否被页面读取。")

    if any(item.kind in {"dom_sink", "source_sink_flow", "ast_data_flow"} for item in findings):
        add("query_js", "Query 脚本探针", "'xsslab_probe_js_2026'", "query", "script", "用于观察脚本字符串附近是否出现探针。")
        if has_form:
            add("form_js", "Form 脚本探针", "'xsslab_probe_form_js_2026'", "form", "script", "用于观察表单输入是否进入脚本上下文。")

    if not candidates:
        add("query_fallback", "基础探针", "xsslab_probe_basic_2026", "query", "summary", "没有明显输入面时，保留一个最基础的验证探针。")

    limit = {"quick": 2, "standard": 3, "deep": 5}.get(mode, 3)
    return candidates[: limit + 2]


def run_ai_multi_round_validation_v2(
    job_id: str,
    page: Page,
    rounds: list[dict[str, str]],
    *,
    use_selenium: bool | None = None,
) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for index, round_item in enumerate(rounds, start=1):
        records = retest_page(
            job_id=job_id,
            page=page,
            payload=str(round_item.get("payload") or ""),
            vector=str(round_item.get("vector") or ""),
            use_selenium=use_selenium,
        )
        outputs.append(
            {
                "round_index": index,
                "round_label": str(round_item.get("label") or f"第 {index} 轮"),
                "candidate_id": str(round_item.get("id") or ""),
                "reason": str(round_item.get("reason") or ""),
                "vector": str(round_item.get("vector") or ""),
                "payload": str(round_item.get("payload") or ""),
                "context": str(round_item.get("context") or ""),
                "records": records,
            }
        )
    return outputs


def suggest_payloads_for_finding(finding: Finding) -> list[dict[str, str]]:
    evidence = _parse_finding_evidence(finding.evidence)
    text = " ".join(
        [
            finding.kind,
            finding.title,
            str(evidence.get("label") or ""),
            str(evidence.get("snippet") or ""),
            str(evidence.get("source") or ""),
            str(evidence.get("flow_display") or ""),
        ]
    ).lower()

    suggestions: list[dict[str, str]] = []

    def add(label: str, payload: str, vector: str = "") -> None:
        item = {
            "label": label,
            "payload": _resolve_payload_alias(payload),
            "vector": vector,
        }
        if item not in suggestions:
            suggestions.append(item)

    if any(token in text for token in ("innerhtml", "document.write", "html()", "insertadjacenthtml", "srcdoc")):
        add("HTML 标签注入", "<img src=x onerror=alert(1)>")
        add("SVG 事件注入", "<svg onload=alert(1)>")

    if any(token in text for token in ("onclick", "onerror", "onload", "inline_event", "html_attr")):
        add("属性闭合注入", '" autofocus onfocus=alert(1) x="')
        add("单引号属性注入", "' onmouseover='alert(1)' x='")

    if any(token in text for token in ("location.search", "query", "document.url", "location.href")):
        add("查询参数反射", "<img src=x onerror=alert(1)>", "query")
        add("查询参数属性逃逸", '" onmouseover="alert(1)', "query")

    if any(token in text for token in ("location.hash", "hashchange")):
        add("Hash 片段注入", "<svg onload=alert(1)>", "hash")

    if any(token in text for token in ("form", "input", "textarea", "select")):
        add("表单回显注入", "<img src=x onerror=alert(1)>", "form")
        add("表单属性逃逸", '" autofocus onfocus=alert(1) x="', "form")

    if any(token in text for token in ("eval", "settimeout", "setinterval", "new function", "script")):
        add("JS 字符串闭合", '";alert(1);//')
        add("JS 单引号闭合", "';alert(1);//")

    if any(token in text for token in ("javascript:", "href", "src")):
        add("协议执行", "javascript:alert(1)")

    add("基础探针", "xsslab_probe_2026")

    return suggestions[:8]


def suggest_payloads_for_page(page: Page, findings: list[Finding]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []

    def add(label: str, payload: str, vector: str = "") -> None:
        item = {
            "label": label,
            "payload": _resolve_payload_alias(payload),
            "vector": vector,
        }
        if item not in suggestions:
            suggestions.append(item)

    for finding in findings:
        for item in suggest_payloads_for_finding(finding):
            add(str(item["label"]), str(item["payload"]), str(item.get("vector") or ""))

    split_result = urlsplit(page.url)
    if parse_qsl(split_result.query, keep_blank_values=True):
        add("页面查询参数", "<img src=x onerror=alert(1)>", "query")
    if "<form" in (page.content or "").lower():
        add("页面表单注入", "<img src=x onerror=alert(1)>", "form")
    if any(signal in (page.content or "") for signal in ("location.hash", "hashchange", "decodeURIComponent(location.hash)")):
        add("页面 Hash 注入", "<svg onload=alert(1)>", "hash")
    add("基础探针", "xsslab_probe_2026")
    return suggestions[:8]


def _verify_query(
    client: httpx.Client, driver: webdriver.Remote | None, page: Page, payload: str, wait_seconds: float
) -> list[VerificationRecord]:
    split_result = urlsplit(page.url)
    params = parse_qsl(split_result.query, keep_blank_values=True)
    if not params:
        return []

    seen: set[str] = set()
    records: list[VerificationRecord] = []
    for name, _ in params:
        if name in seen:
            continue
        seen.add(name)
        mutated = [(key, payload if key == name else value) for key, value in params]
        target_url = urlunsplit(
            (
                split_result.scheme,
                split_result.netloc,
                split_result.path,
                urlencode(mutated, doseq=True),
                split_result.fragment,
            )
        )
        records.append(_request_and_check(client, driver, page, target_url, "query", name, payload, method="get", wait_seconds=wait_seconds))
    return records


def _verify_forms(
    client: httpx.Client, driver: webdriver.Remote | None, page: Page, payload: str, wait_seconds: float
) -> list[VerificationRecord]:
    if not page.content:
        return []
    try:
        document = lxml_html.fromstring(page.content)
    except Exception:
        return []

    records: list[VerificationRecord] = []
    forms = document.xpath("//form")[: get_int("DYNAMIC_VERIFY_MAX_FORMS_PER_PAGE", 3)]
    for index, form in enumerate(forms, start=1):
        field_names: list[str] = []
        for field in form.xpath(".//input|.//textarea|.//select"):
            field_type = (field.get("type") or "").lower()
            name = field.get("name")
            if not name or field_type in {"submit", "button", "image", "reset", "file"}:
                continue
            field_names.append(name)
        if not field_names:
            continue

        action = form.get("action") or page.url
        target_url = urljoin(page.url, action)
        method = (form.get("method") or "get").lower()
        form_data = {name: payload for name in field_names[:5]}
        records.append(
            _request_and_check(
                client,
                driver,
                page,
                target_url,
                "form",
                ",".join(field_names[:5]) or f"form_{index}",
                payload,
                method=method,
                data=form_data,
                wait_seconds=wait_seconds,
            )
        )
    return records


def _verify_hash(page: Page, payload: str, selenium_enabled: bool) -> list[VerificationRecord]:
    content = page.content or ""
    hash_signals = ("location.hash", "hashchange", "decodeURIComponent(location.hash)")
    if not any(signal in content for signal in hash_signals):
        return []

    target_url = page.url.split("#", 1)[0] + "#" + payload
    evidence = "页面脚本包含 location.hash 相关逻辑，建议配合 Selenium 做进一步验证。"
    return [
        VerificationRecord(
            page_id=page.id,
            page_url=page.url,
            target_url=target_url,
            vector="hash",
            engine="selenium" if selenium_enabled else "http",
            parameter_name="location.hash",
            payload=payload,
            status="suspected",
            evidence=evidence,
            reflection_found=False,
            reflection_context="dom_hash",
            reflection_snippet=None,
            context_hint="页面存在 location.hash 相关逻辑，更像前端 DOM 读取场景，建议继续结合浏览器行为确认。",
        )
    ]


def _verify_hash_runtime(
    client: httpx.Client,
    driver: webdriver.Remote | None,
    page: Page,
    payload: str,
    wait_seconds: float,
) -> list[VerificationRecord]:
    content = page.content or ""
    hash_signals = ("location.hash", "hashchange", "decodeURIComponent(location.hash)")
    if not any(signal in content for signal in hash_signals):
        return []

    target_url = page.url.split("#", 1)[0] + "#" + payload
    if driver is not None:
        return [
            _request_and_check(
                client,
                driver,
                page,
                target_url,
                "hash",
                "location.hash",
                payload,
                method="get",
                wait_seconds=wait_seconds,
            )
        ]

    return _verify_hash(page, payload, False)


def _plan_verification_vectors(page: Page, findings: list[Finding]) -> list[str]:
    hints: set[str] = set()
    content = page.content or ""
    split_result = urlsplit(page.url)
    has_query = bool(parse_qsl(split_result.query, keep_blank_values=True))
    has_form = "<form" in content.lower()

    for finding in findings:
        evidence = _parse_finding_evidence(finding.evidence)
        text = " ".join(
            [
                finding.kind,
                finding.title,
                str(evidence.get("label") or ""),
                str(evidence.get("snippet") or ""),
                str(evidence.get("source") or ""),
                str(evidence.get("flow_display") or ""),
            ]
        ).lower()
        if any(token in text for token in ("location.hash", "hashchange")):
            hints.add("hash")
        if any(token in text for token in ("location.search", "query", "document.url", "location.href")):
            hints.add("query")
        if any(token in text for token in ("form", "input", "textarea", "select")):
            hints.add("form")

    vectors: list[str] = []
    if "query" in hints and has_query:
        vectors.append("query")
    if "hash" in hints:
        vectors.append("hash")
    if "form" in hints and has_form:
        vectors.append("form")

    fallback_vectors: list[str] = []
    if has_query:
        fallback_vectors.append("query")
    if has_form:
        fallback_vectors.append("form")
    if any(signal in content for signal in ("location.hash", "hashchange", "decodeURIComponent(location.hash)")):
        fallback_vectors.append("hash")

    ordered_vectors: list[str] = []
    for vector in vectors + fallback_vectors:
        if vector not in ordered_vectors:
            ordered_vectors.append(vector)
    return ordered_vectors


def _parse_finding_evidence(raw: str) -> dict[str, object]:
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {"snippet": raw}


def _wait_for_browser_idle(driver: webdriver.Remote, wait_seconds: float) -> None:
    deadline = time.time() + max(wait_seconds, 0.5)
    last_html = ""
    stable_rounds = 0
    while time.time() < deadline:
        try:
            ready = str(driver.execute_script("return document.readyState || ''")).lower()
            current_html = str(
                driver.execute_script("return document.documentElement ? document.documentElement.outerHTML : ''")
                or ""
            )
        except Exception:
            time.sleep(0.1)
            continue
        if ready == "complete" and current_html == last_html:
            stable_rounds += 1
            if stable_rounds >= 2:
                return
        else:
            stable_rounds = 0
        last_html = current_html
        time.sleep(0.15)
    if wait_seconds > 0:
        time.sleep(min(wait_seconds, 1.0))


def _collect_browser_result(
    driver: webdriver.Remote,
    wait_seconds: float,
) -> tuple[str, str | None, str | None]:
    _wait_for_browser_idle(driver, wait_seconds)
    alert_text = None
    try:
        alert = driver.switch_to.alert
        alert_text = str(alert.text or "").strip() or None
        alert.accept()
    except NoAlertPresentException:
        pass
    except WebDriverException:
        pass

    dom_text = ""
    current_url = None
    try:
        dom_text = str(
            driver.execute_script("return document.documentElement ? document.documentElement.outerHTML : '';")
            or ""
        )
    except Exception:
        try:
            dom_text = str(driver.page_source or "")
        except Exception:
            dom_text = ""
    try:
        current_url = str(driver.current_url or "")
    except Exception:
        current_url = None
    return dom_text, alert_text, current_url


def _submit_with_driver(
    driver: webdriver.Remote,
    page_url: str,
    target_url: str,
    method: str,
    data: dict[str, str] | None,
    wait_seconds: float,
) -> tuple[str, str | None, str | None]:
    if method.lower() == "get":
        driver.get(target_url)
        return _collect_browser_result(driver, wait_seconds)

    driver.get(page_url)
    _wait_for_browser_idle(driver, min(wait_seconds, 1.0))
    payload_data = dict(data or {})
    driver.execute_script(
        """
        const targetUrl = arguments[0];
        const method = arguments[1];
        const fields = arguments[2];
        const form = document.createElement('form');
        form.method = method;
        form.action = targetUrl;
        form.style.display = 'none';
        for (const [name, value] of Object.entries(fields)) {
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = name;
          input.value = value;
          form.appendChild(input);
        }
        document.body.appendChild(form);
        form.submit();
        """,
        target_url,
        method.lower(),
        payload_data,
    )
    return _collect_browser_result(driver, wait_seconds)


def _classify_runtime_result(
    text: str,
    payload: str,
    *,
    alert_text: str | None = None,
    browser_url: str | None = None,
) -> tuple[str, str | None, bool, str | None, str | None, str | None]:
    if not text:
        if alert_text:
            evidence = f"浏览器出现弹窗：{alert_text}"
            if browser_url:
                evidence = f"{evidence} @ {browser_url}"
            return "verified", evidence, True, "script", evidence, "浏览器侧已经出现可见脚本执行信号，说明当前 payload 很可能已进入可执行上下文。"
        return "not_triggered", None, False, None, None, "响应内容为空，没有观察到可用于定位的回显信号。"

    candidates = [payload, html.escape(payload), payload.replace('"', "&quot;")]
    for candidate in candidates:
        idx = text.find(candidate)
        if idx != -1:
            start = max(0, idx - 80)
            end = min(len(text), idx + len(candidate) + 80)
            snippet = text[start:end].replace("\n", " ")
            context = _guess_reflection_context(text, idx, len(candidate))
            hint = _context_hint(context)
            if alert_text:
                hint = f"{hint} 同时浏览器还出现了弹窗信号：{alert_text}"
            return "verified", snippet, True, context, snippet, hint

    if alert_text:
        evidence = f"浏览器出现弹窗：{alert_text}"
        if browser_url:
            evidence = f"{evidence} @ {browser_url}"
        return "verified", evidence, True, "script", evidence, "虽然页面源码中没有直接找到稳定回显，但浏览器已经出现弹窗，这通常比单纯回显更接近真实执行结果。"

    return "not_triggered", None, False, None, None, "没有在响应内容中直接观察到 payload 回显，可能需要换更匹配当前上下文的探针继续验证。"


def _request_and_check(
    client: httpx.Client,
    driver: webdriver.Remote | None,
    page: Page,
    target_url: str,
    vector: str,
    parameter_name: str | None,
    payload: str,
    method: str,
    data: dict[str, str] | None = None,
    wait_seconds: float = 0.0,
) -> VerificationRecord:
    try:
        alert_text = None
        browser_url = None
        if driver is not None:
            text, alert_text, browser_url = _submit_with_driver(
                driver,
                page.url,
                target_url,
                method,
                data,
                wait_seconds,
            )
            engine = "selenium"
        elif method == "post":
            response = client.post(target_url, data=data or {})
            text = response.text
            engine = "http"
        else:
            response = client.get(target_url, params=data or None)
            text = response.text
            engine = "http"
        status, evidence, reflection_found, reflection_context, reflection_snippet, context_hint = _classify_runtime_result(
            text, payload, alert_text=alert_text, browser_url=browser_url
        )
    except Exception as exc:
        engine = "selenium" if driver is not None else "http"
        status = "error"
        evidence = f"{type(exc).__name__}: {exc}"
        reflection_found = False
        reflection_context = None
        reflection_snippet = None
        context_hint = "本次请求执行失败，因此没有得到有效回显定位结果。"
    return VerificationRecord(
        page_id=page.id,
        page_url=page.url,
        target_url=target_url,
        vector=vector,
        engine=engine,
        parameter_name=parameter_name,
        payload=payload,
        status=status,
        evidence=evidence,
        reflection_found=reflection_found,
        reflection_context=reflection_context,
        reflection_snippet=reflection_snippet,
        context_hint=context_hint,
    )


def _classify_response(
    text: str,
    payload: str,
    *,
    alert_text: str | None = None,
    browser_url: str | None = None,
) -> tuple[str, str | None, bool, str | None, str | None, str | None]:
    if not text:
        return "not_triggered", None, False, None, None, "响应内容为空，没有观察到可用于定位的回显信号。"
    candidates = [payload, html.escape(payload), payload.replace('"', "&quot;")]
    for candidate in candidates:
        idx = text.find(candidate)
        if idx != -1:
            start = max(0, idx - 80)
            end = min(len(text), idx + len(candidate) + 80)
            snippet = text[start:end].replace("\n", " ")
            context = _guess_reflection_context(text, idx, len(candidate))
            return "verified", snippet, True, context, snippet, _context_hint(context)
    return "not_triggered", None, False, None, None, "没有在响应内容中直接观察到 payload 回显，可能需要换上下文更匹配的探针继续验证。"


def _emit(log: Callable[[str], None] | None, message: str) -> None:
    if log:
        log(message)


def _pack_evidence(engine: str, detail: str | None, **extra: object) -> str | None:
    if detail is None and not extra:
        return None
    payload: dict[str, object] = {"engine": engine, "detail": detail}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _guess_reflection_context(text: str, index: int, length: int) -> str:
    window_start = max(0, index - 160)
    window_end = min(len(text), index + length + 160)
    around = text[window_start:window_end].lower()
    before = text[window_start:index].lower()
    if "<script" in around and "</script>" in around:
        return "script"
    if "<!--" in around and "-->" in around:
        return "comment"
    if re.search(r"<[^>]+=\s*['\"][^'\"]*$", before):
        return "html_attr"
    if "<" in before and ">" in around:
        return "html_text"
    return "unknown"


def _context_hint(context: str | None) -> str:
    return {
        "html_text": "payload 看起来出现在 HTML 文本区域，说明输入至少进入了页面结构化内容。",
        "html_attr": "payload 看起来出现在 HTML 属性值附近，需要重点检查引号逃逸和事件属性风险。",
        "script": "payload 看起来出现在 script 上下文附近，建议优先检查字符串闭合和脚本拼接逻辑。",
        "comment": "payload 出现在注释附近，说明存在回显，但当前上下文未必能直接执行。",
        "dom_hash": "当前结果更像前端读取 hash 后参与 DOM 处理的场景，建议继续结合浏览器行为确认。",
        "unknown": "payload 已被回显，但暂时无法稳定判断所属上下文，建议继续结合源码和页面行为确认。",
    }.get(context or "", "当前结果主要用于提示输入已可达，仍需结合上下文继续判断风险强度。")


def _init_driver(timeout: float) -> webdriver.Remote:
    try:
        opts = ChromeOptions()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1440,960")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--ignore-certificate-errors")
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(int(timeout))
        return driver
    except Exception:
        opts = FirefoxOptions()
        opts.add_argument("--headless")
        opts.add_argument("--width=1440")
        opts.add_argument("--height=960")
        driver = webdriver.Firefox(options=opts)
        driver.set_page_load_timeout(int(timeout))
        return driver
