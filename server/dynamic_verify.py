"""轻量动态验证模块。"""
from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from lxml import html as lxml_html
from selenium import webdriver
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

    payload = str(get("DYNAMIC_VERIFY_PAYLOAD", "xsslab_verify_payload_2026"))
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
                vectors = _plan_verification_vectors(page, findings_by_url.get(page.url, []))
                _emit(log, f"[动态验证] 页面 {page.url} 计划验证向量: {', '.join(vectors) if vectors else 'none'}")
                if "query" in vectors:
                    records.extend(_verify_query(client, driver, page, payload, wait_seconds))
                if "form" in vectors:
                    records.extend(_verify_forms(client, driver, page, payload, wait_seconds))
                if "hash" in vectors:
                    records.extend(_verify_hash(page, payload, driver is not None))
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
                evidence=_pack_evidence(record.engine, record.evidence),
            )
        )
    db.session.commit()
    verified_count = sum(1 for item in records if item.status == "verified")
    _emit(log, f"[动态验证] 完成，共生成 {len(records)} 条结果，已触发 {verified_count} 条")
    return len(records)


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
        )
    ]


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
        if driver is not None and method == "get":
            driver.get(target_url)
            time.sleep(wait_seconds)
            text = driver.page_source
            engine = "selenium"
        elif method == "post":
            response = client.post(target_url, data=data or {})
            text = response.text
            engine = "http"
        else:
            response = client.get(target_url, params=data or None)
            text = response.text
            engine = "http"
        status, evidence = _classify_response(text, payload)
    except Exception as exc:
        engine = "selenium" if driver is not None and method == "get" else "http"
        status = "error"
        evidence = f"{type(exc).__name__}: {exc}"
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
    )


def _classify_response(text: str, payload: str) -> tuple[str, str | None]:
    if not text:
        return "not_triggered", None
    candidates = [payload, html.escape(payload), payload.replace('"', "&quot;")]
    for candidate in candidates:
        idx = text.find(candidate)
        if idx != -1:
            start = max(0, idx - 80)
            end = min(len(text), idx + len(candidate) + 80)
            return "verified", text[start:end].replace("\n", " ")
    return "not_triggered", None


def _emit(log: Callable[[str], None] | None, message: str) -> None:
    if log:
        log(message)


def _pack_evidence(engine: str, detail: str | None) -> str | None:
    if detail is None:
        return None
    return json.dumps({"engine": engine, "detail": detail}, ensure_ascii=False)


def _init_driver(timeout: float) -> webdriver.Remote:
    try:
        opts = ChromeOptions()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(int(timeout))
        return driver
    except Exception:
        opts = FirefoxOptions()
        opts.add_argument("--headless")
        driver = webdriver.Firefox(options=opts)
        driver.set_page_load_timeout(int(timeout))
        return driver
