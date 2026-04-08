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

SOURCE_EXPR_PATTERNS = [
    (r"\blocation\.search\b", "location.search"),
    (r"\blocation\.hash\b", "location.hash"),
    (r"\blocation\.href\b", "location.href"),
    (r"\bdocument\.(?:URL|documentURI|baseURI)\b", "document.URL"),
    (r"\bdocument\.cookie\b", "document.cookie"),
    (r"\b(?:localStorage|sessionStorage)\b", "storage"),
    (r"\bwindow\.name\b", "window.name"),
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
SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(?P<body>.*?)</script>", re.I | re.S)
ASSIGN_RE = re.compile(r"^(?:const|let|var)?\s*([A-Za-z_$][\w$]*)\s*=\s*(.+)$", re.S)
SINK_ASSIGN_RE = re.compile(r"(.+?\.(?:innerHTML|outerHTML|srcdoc))\s*=\s*(.+)$", re.S)
INSERT_HTML_RE = re.compile(r"insertAdjacentHTML\s*\(\s*[^,]+,\s*(.+?)\)$", re.S)
WRITE_RE = re.compile(r"document\.write(?:ln)?\s*\(\s*(.+?)\s*\)$", re.S)
EVAL_RE = re.compile(r"(?:eval|setTimeout|setInterval)\s*\(\s*(.+?)\s*\)$", re.S)
HTML_CALL_RE = re.compile(r"\.html\s*\(\s*(.+?)\s*\)$", re.S)
IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][\w$]*\b")
EXECUTABLE_ATTR_RE = re.compile(
    r"<(?P<tag>[a-zA-Z0-9:_-]+)(?P<body>[^>]*?\s(?P<attr>href|src|action|formaction)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)[^>]*)>",
    re.I | re.S,
)


def analyze_html(html: str) -> Iterable[StaticFinding]:
    if not html:
        return []

    findings: list[StaticFinding] = []
    seen: set[tuple[str, str, str]] = set()

    def add(
        kind: str,
        severity: str,
        title: str,
        snippet: str,
        line: int,
        label: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload_obj = {
            "line": line,
            "label": label,
            "snippet": _normalize_ws(snippet)[:500],
        }
        if extra:
            payload_obj.update(extra)
        payload = json.dumps(payload_obj, ensure_ascii=False)
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

    _analyze_script_flows(html, add)

    script_count = html.lower().count("<script")
    if script_count > 20:
        add("anomaly", "low", "脚本标签数量异常", f"检测到 {script_count} 个 script 标签", 1, "script_count")

    return findings


def _line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _analyze_script_flows(html: str, add) -> None:
    for script_match in SCRIPT_BLOCK_RE.finditer(html):
        script_body = script_match.group("body") or ""
        if not script_body.strip():
            continue
        base_offset = script_match.start("body")
        tainted_vars: dict[str, dict[str, object]] = {}
        for raw_statement, start in _split_statements(script_body):
            statement = raw_statement.strip()
            if not statement:
                continue

            line = _line_of_offset(html, base_offset + start)

            assign_match = ASSIGN_RE.match(statement)
            if assign_match:
                flow = _find_source_flow(assign_match.group(2).strip(), tainted_vars)
                if flow:
                    tainted_vars[assign_match.group(1)] = {
                        "source": flow["source"],
                        "path": list(flow.get("path") or []) + [assign_match.group(1)],
                    }

            sink_match = SINK_ASSIGN_RE.match(statement)
            if sink_match:
                flow = _find_source_flow(sink_match.group(2).strip(), tainted_vars)
                if flow:
                    sink_target = sink_match.group(1).strip()
                    flow_display = _build_flow_display(flow["source"], flow.get("path") or [], sink_target)
                    add(
                        "ast_data_flow",
                        "high",
                        "Script data flow to dangerous sink",
                        statement,
                        line,
                        flow_display,
                        {
                            "source": flow["source"],
                            "path": flow.get("path") or [],
                            "sink": sink_target,
                            "flow_display": flow_display,
                        },
                    )

            for pattern, sink_label in (
                (INSERT_HTML_RE, "insertAdjacentHTML"),
                (WRITE_RE, "document.write"),
                (EVAL_RE, "eval/setTimeout"),
                (HTML_CALL_RE, "jquery.html"),
            ):
                call_match = pattern.search(statement)
                if not call_match:
                    continue
                flow = _find_source_flow(call_match.group(1).strip(), tainted_vars)
                if flow:
                    flow_display = _build_flow_display(flow["source"], flow.get("path") or [], sink_label)
                    add(
                        "ast_data_flow",
                        "high",
                        "Script data flow to dangerous sink",
                        statement,
                        line,
                        flow_display,
                        {
                            "source": flow["source"],
                            "path": flow.get("path") or [],
                            "sink": sink_label,
                            "flow_display": flow_display,
                        },
                    )
                    break


def _split_statements(script: str) -> list[tuple[str, int]]:
    statements: list[tuple[str, int]] = []
    start = 0
    in_single = False
    in_double = False
    in_template = False
    escaped = False

    for idx, ch in enumerate(script):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and (in_single or in_double or in_template):
            escaped = True
            continue
        if ch == "'" and not in_double and not in_template:
            in_single = not in_single
        elif ch == '"' and not in_single and not in_template:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_template = not in_template
        elif ch == ";" and not in_single and not in_double and not in_template:
            statements.append((script[start:idx], start))
            start = idx + 1

    tail = script[start:]
    if tail.strip():
        statements.append((tail, start))
    return statements


def _find_source_flow(expr: str, tainted_vars: dict[str, dict[str, object]]) -> dict[str, object] | None:
    for pattern, label in SOURCE_EXPR_PATTERNS:
        if re.search(pattern, expr):
            return {"source": label, "path": []}
    for name in IDENTIFIER_RE.findall(expr):
        if name in tainted_vars:
            return {
                "source": tainted_vars[name]["source"],
                "path": list(tainted_vars[name].get("path") or []),
            }
    return None


def _build_flow_display(source: str, path: list[object], sink: str) -> str:
    chain = [source]
    chain.extend(str(item) for item in path if item)
    chain.append(sink)
    return " -> ".join(chain)


def _extract_snippet(text: str, start: int, end: int, window: int = 80) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return text[left:right]


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())
