"""基础 XSS 静态分析器。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StaticFinding:
    kind: str
    severity: str
    title: str
    evidence: str


SOURCE_PATTERNS = [
    ("location_search", r"location\.search", "URL 查询参数 location.search"),
    ("location_hash", r"location\.hash", "URL 片段 location.hash"),
    ("location_href", r"location\.href", "当前 URL location.href"),
    ("document_url", r"document\.(URL|documentURI|baseURI)", "文档 URL document.URL"),
    ("document_cookie", r"document\.cookie", "Cookie document.cookie"),
    ("storage", r"(localStorage|sessionStorage)", "本地存储 localStorage/sessionStorage"),
    ("window_name", r"window\.name", "窗口名称 window.name"),
]

SINK_PATTERNS = [
    ("innerHTML", "medium", r"\.innerHTML\s*=", "危险 DOM Sink: innerHTML"),
    ("outerHTML", "medium", r"\.outerHTML\s*=", "危险 DOM Sink: outerHTML"),
    ("document_write", "high", r"document\.write(?:ln)?\s*\(", "危险 DOM Sink: document.write"),
    ("insert_adjacent_html", "medium", r"insertAdjacentHTML\s*\(", "危险 DOM Sink: insertAdjacentHTML"),
    ("iframe_srcdoc", "high", r"\.srcdoc\s*=|srcdoc\s*=", "危险 DOM Sink: iframe srcdoc"),
    ("eval", "high", r"eval\s*\(", "危险脚本执行点: eval"),
    ("new_function", "high", r"new\s+Function\s*\(", "危险脚本执行点: new Function"),
    ("settimeout_string", "medium", r"setTimeout\s*\(\s*['\"]", "危险脚本执行点: setTimeout"),
    ("setinterval_string", "medium", r"setInterval\s*\(\s*['\"]", "危险脚本执行点: setInterval"),
    ("jquery_html", "medium", r"\.html\s*\(", "危险 DOM Sink: jQuery html()"),
]

INLINE_EVENT_RE = re.compile(
    r"<(?P<tag>[a-zA-Z0-9:_-]+)(?P<body>[^>]*?\s(?P<attr>on[a-zA-Z0-9_-]+)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)[^>]*)>",
    re.I | re.S,
)
EXECUTABLE_ATTR_RE = re.compile(
    r"<(?P<tag>[a-zA-Z0-9:_-]+)(?P<body>[^>]*?\s(?P<attr>href|src|action|formaction)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)[^>]*)>",
    re.I | re.S,
)


def analyze_html(html: str) -> Iterable[StaticFinding]:
    if not html:
        return []

    findings: list[StaticFinding] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, severity: str, title: str, snippet: str, line: int, label: str) -> None:
        payload = json.dumps(
            {
                "line": line,
                "label": label,
                "snippet": _normalize_ws(snippet)[:500],
            },
            ensure_ascii=False,
        )
        key = (kind, title, payload)
        if key in seen:
            return
        seen.add(key)
        findings.append(StaticFinding(kind=kind, severity=severity, title=title, evidence=payload))

    for match in INLINE_EVENT_RE.finditer(html):
        attr_value = (match.group("value") or "").lower()
        severity = "medium"
        if any(token in attr_value for token in ("location.href", "window.location", "eval(", "innerhtml", "document.write")):
            severity = "high"
        add(
            "inline_event_handler",
            severity,
            "内联事件处理器风险",
            match.group(0),
            _line_of_offset(html, match.start()),
            match.group("attr"),
        )

    for match in EXECUTABLE_ATTR_RE.finditer(html):
        attr = match.group("attr").lower()
        value = match.group("value").strip().lower()
        line = _line_of_offset(html, match.start())
        snippet = match.group(0)
        if value.startswith("javascript:"):
            add("javascript_protocol", "high", "执行型 javascript: 协议风险", snippet, line, attr)
        if value.startswith("data:text/html"):
            add("data_protocol", "high", "可执行 data:text/html 协议风险", snippet, line, attr)

    source_hits: list[tuple[str, int, str]] = []
    for source_key, pattern, label in SOURCE_PATTERNS:
        for match in re.finditer(pattern, html, re.I):
            source_hits.append((source_key, _line_of_offset(html, match.start()), label))

    for sink_name, default_severity, pattern, title in SINK_PATTERNS:
        for match in re.finditer(pattern, html, re.I):
            severity = "high" if source_hits and default_severity != "high" else default_severity
            add(
                "dom_sink",
                severity,
                title,
                _extract_snippet(html, match.start(), match.end()),
                _line_of_offset(html, match.start()),
                sink_name,
            )

    seen_sources: set[str] = set()
    for source_key, line, label in source_hits:
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        add("tainted_source", "low", "潜在用户可控输入源", label, line, source_key)

    if source_hits and any(f.kind == "dom_sink" for f in findings):
        first_line = source_hits[0][1]
        source_labels = ", ".join(dict.fromkeys(label for _, _, label in source_hits))
        add("source_sink_flow", "high", "DOM XSS 数据流风险", source_labels, first_line, "source+sink")

    for match in re.finditer(r"location\.(href|replace|assign)\s*=", html, re.I):
        add(
            "javascript_redirection",
            "low",
            "JavaScript 重定向风险",
            _extract_snippet(html, match.start(), match.end()),
            _line_of_offset(html, match.start()),
            "location",
        )

    script_count = html.lower().count("<script")
    if script_count > 20:
        add("anomaly", "low", "脚本标签数量异常", f"检测到 {script_count} 个 script 标签", 1, "script_count")

    return findings


def _line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _extract_snippet(text: str, start: int, end: int, window: int = 80) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return text[left:right]


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())
