"""
漏洞审计分析引擎
作用：通过正则匹配和 DOM 树解析，识别 HTML/JS 中的内联事件、危险 Sink 点和伪协议等 XSS 风险。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from parsel import Selector


@dataclass(frozen=True)
class StaticFinding:
    kind: str
    severity: str
    title: str
    evidence: str


# 常见的 DOM XSS 接收器正则模式
_DOM_SINKS = [
    ("dom_sink", "medium", "潜在的 DOM XSS 接收器: innerHTML", r"\.innerHTML\s*="),
    ("dom_sink", "medium", "潜在的 DOM XSS 接收器: outerHTML", r"\.outerHTML\s*="),
    ("dom_sink", "high", "潜在的 DOM XSS 接收器: document.write", r"document\.write\s*\("),
    ("dom_sink", "high", "潜在的 DOM XSS 接收器: document.writeln", r"document\.writeln\s*\("),
    ("dom_sink", "high", "潜在的危险函数调用: eval", r"eval\s*\("),
    ("dom_sink", "low", "潜在的 DOM XSS 接收器: setTimeout", r"setTimeout\s*\("),
    ("dom_sink", "low", "潜在的 DOM XSS 接收器: setInterval", r"setInterval\s*\("),
    ("dom_sink", "low", "潜在的 DOM XSS 接收器: insertAdjacentHTML", r"insertAdjacentHTML\s*\("),
    ("dom_sink", "low", "潜在的 DOM XSS 接收器: jQuery html()", r"\.html\s*\("),
]


def analyze_html(html: str) -> Iterable[StaticFinding]:
    """对 HTML 内容进行深度静态安全审计"""
    sel = Selector(text=html)

    # 1. 扫描所有标签的属性
    for el in sel.xpath("//*"):
        tag_name = el.root.tag
        attrs = el.attrib
        for k, v in attrs.items():
            k_lower = k.lower()
            v_lower = v.lower()

            # 扫描内联事件处理器 (如 onclick, onerror)
            if k_lower.startswith("on"):
                yield StaticFinding(
                    kind="inline_event_handler",
                    severity="low",
                    title="存在内联事件处理器属性 (如 onclick)",
                    evidence=f"<{tag_name} {k}={v!r}>",
                )

            # 扫描危险的伪协议 (如 href="javascript:...")
            if k_lower in ("href", "src", "action", "formaction"):
                if v_lower.startswith("javascript:"):
                    yield StaticFinding(
                        kind="javascript_protocol",
                        severity="medium",
                        title="检测到危险的 javascript: 协议",
                        evidence=f"<{tag_name} {k}={v!r}>",
                    )
                elif v_lower.startswith("data:text/html"):
                    yield StaticFinding(
                        kind="data_protocol",
                        severity="medium",
                        title="检测到危险的 data: 协议 (可能导致 XSS)",
                        evidence=f"<{tag_name} {k}={v!r}>",
                    )

    # 2. 扫描 JavaScript 代码块中的风险模式 (包括内联脚本和属性中的脚本)
    # 我们直接对全量 HTML 进行正则扫描，以防漏掉混在属性中的逻辑
    
    # 扫描重定向
    if re.search(r"location\.(href|replace|assign)\s*=", html, re.I):
        yield StaticFinding(
            kind="javascript_redirection",
            severity="low",
            title="检测到 JavaScript 重定向逻辑",
            evidence="匹配到 location.href/replace/assign",
        )

    # 扫描 DOM Sinks
    for kind, severity, title, pat in _DOM_SINKS:
        if re.search(pat, html, re.I):
            yield StaticFinding(
                kind=kind,
                severity=severity,
                title=title,
                evidence=f"正则匹配: {pat}",
            )

    # 3. 扫描特殊的 HTML 注入点
    # 如果页面中存在未转义的 <script> 标签（可能是用户输入反射回来的）
    # 这里我们通过统计 <script> 标签数量并结合一些特征来辅助判断（实际注入需动态验证，此处仅作提示）
    if html.count("<script") > 20:
        yield StaticFinding(
            kind="anomaly",
            severity="low",
            title="脚本标签数量异常过多",
            evidence=f"检测到 {html.count('<script')} 个 script 标签",
        )
