"""基于 ESTree AST 的 JavaScript 污点分析模块。

使用 esprima-python 将 <script> 块解析为 AST，在 AST 层面实现
从污点源（location.search 等）到危险 Sink（innerHTML 等）的数据流追踪。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

import esprima

# ---------------------------------------------------------------------------
# 污点源定义
# ---------------------------------------------------------------------------

# MemberExpression 形式的污点源: (对象名, 属性名) → 源标签
_SOURCE_MEMBERS: dict[tuple[str, str], str] = {
    ("location", "search"): "location.search",
    ("location", "hash"): "location.hash",
    ("location", "href"): "location.href",
    ("document", "URL"): "document.URL",
    ("document", "documentURI"): "document.URL",
    ("document", "baseURI"): "document.URL",
    ("document", "cookie"): "document.cookie",
    ("document", "referrer"): "document.referrer",
    ("window", "name"): "window.name",
}

# Identifier 形式的污点源
_SOURCE_IDENTIFIERS: dict[str, str] = {
    "localStorage": "storage",
    "sessionStorage": "storage",
}

# ---------------------------------------------------------------------------
# Sink 定义
# ---------------------------------------------------------------------------

# 赋值型 Sink: MemberExpression 属性名
_SINK_ASSIGN_PROPS: set[str] = {
    "innerHTML", "outerHTML", "srcdoc",
}

# 调用型 Sink: (对象名, 方法名) — None 表示全局函数
_SINK_CALLS: set[tuple[str | None, str]] = {
    ("document", "write"),
    ("document", "writeln"),
    (None, "eval"),
    (None, "setTimeout"),
    (None, "setInterval"),
}

# new 表达式 Sink
_SINK_NEW_CALLS: set[str] = {"Function"}

# 方法调用型 Sink: 方法名 → 标签
_SINK_METHOD_CALLS: dict[str, str] = {
    "insertAdjacentHTML": "insertAdjacentHTML",
    "html": "jquery.html",
}

# ---------------------------------------------------------------------------
# 污点传播规则
# ---------------------------------------------------------------------------

# 包装函数: 第一个参数污点则返回值污点
_WRAPPER_FUNCTIONS: set[str] = {
    "decodeURIComponent", "encodeURIComponent", "escape", "unescape",
    "String", "Number", "Boolean",
    "atob", "btoa",
}

# 污点对象上的方法调用，返回值继承污点
_PROPAGATING_METHODS: set[str] = {
    "get", "toString", "valueOf", "has", "entries", "keys", "values",
    "substring", "slice", "substr", "trim", "trimStart", "trimEnd",
    "replace", "replaceAll", "split", "concat", "match", "matchAll",
    "normalize", "padStart", "padEnd", "repeat", "toLowerCase", "toUpperCase",
    "toLocaleLowerCase", "toLocaleUpperCase", "charAt", "charCodeAt",
    "codePointAt", "includes", "startsWith", "endsWith", "indexOf",
    "lastIndexOf", "search", "encodeURI", "decodeURI",
}

# 构造器传播: 第一个参数污点则实例污点
_TAINTED_CONSTRUCTORS: set[str] = {
    "URLSearchParams", "URL", "Request",
}

# ---------------------------------------------------------------------------
# Script 块提取正则
# ---------------------------------------------------------------------------
_SCRIPT_BLOCK_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.I | re.S
)
_SCRIPT_TYPE_RE = re.compile(r'type\s*=\s*["\']([^"\']+)["\']', re.I)


# ---------------------------------------------------------------------------
# 污点信息
# ---------------------------------------------------------------------------
@dataclass
class TaintInfo:
    source: str
    path: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------

def analyze_script_flows(html: str, add: Callable) -> None:
    """分析 HTML 中所有 <script> 块的 AST 数据流。"""
    for match in _SCRIPT_BLOCK_RE.finditer(html):
        attrs = match.group("attrs") or ""
        body = match.group("body") or ""
        if not body.strip():
            continue

        # 跳过非 JS 类型的 script
        type_match = _SCRIPT_TYPE_RE.search(attrs)
        if type_match:
            script_type = type_match.group(1).lower()
            if script_type not in ("text/javascript", "application/javascript", "module", ""):
                continue

        base_offset = match.start("body")
        base_line = html.count("\n", 0, base_offset) + 1

        try:
            ast = esprima.parseScript(body, tolerant=True, loc=True, range=True) # 解析 JS AST
        except Exception:
            continue

        _walk_and_emit(ast, add, base_line, body, html) # 遍历 AST 并输出发现


# ---------------------------------------------------------------------------
# AST 语句遍历器
# ---------------------------------------------------------------------------

def _walk_and_emit(
    ast: Any,
    add: Callable,
    script_base_line: int,
    script_body: str,
    html: str,
) -> None:
    tainted_vars: dict[str, TaintInfo] = {}
    _walk_statements(ast.body, tainted_vars, add, script_base_line, script_body, html) # 从顶层语句开始追踪


def _walk_statements(
    statements: list[Any],
    tainted_vars: dict[str, TaintInfo],
    add: Callable,
    script_base_line: int,
    script_body: str,
    html: str,
) -> None:
    for stmt in statements:
        try:
            _process_statement(stmt, tainted_vars, add, script_base_line, script_body, html) # 分析单条语句
        except Exception:
            continue


def _process_statement(
    stmt: Any,
    tainted_vars: dict[str, TaintInfo],
    add: Callable,
    script_base_line: int,
    script_body: str,
    html: str,
) -> None:
    stmt_type = stmt.type

    if stmt_type == "VariableDeclaration":
        for decl in stmt.declarations:
            if decl.init is not None:
                taint = _eval_taint(decl.init, tainted_vars)
                if taint is not None and decl.id.type == "Identifier":
                    tainted_vars[decl.id.name] = TaintInfo(
                        source=taint.source,
                        path=taint.path + [decl.id.name],
                    )
                # 检查 init 是否为 Sink 调用
                _check_call_sink(decl.init, tainted_vars, add, script_base_line, script_body)

    elif stmt_type == "ExpressionStatement":
        expr = stmt.expression
        if expr.type == "AssignmentExpression" and expr.operator == "=":
            _handle_assignment(expr, tainted_vars, add, script_base_line, script_body)
        elif expr.type == "CallExpression":
            _check_call_sink(expr, tainted_vars, add, script_base_line, script_body)

    elif stmt_type == "FunctionDeclaration":
        if stmt.body and stmt.body.body:
            _walk_statements(stmt.body.body, tainted_vars, add, script_base_line, script_body, html)

    elif stmt_type in ("IfStatement",):
        if stmt.consequent:
            if stmt.consequent.type == "BlockStatement":
                _walk_statements(stmt.consequent.body, tainted_vars, add, script_base_line, script_body, html)
            else:
                _process_statement(stmt.consequent, tainted_vars, add, script_base_line, script_body, html)
        if stmt.alternate:
            if stmt.alternate.type == "BlockStatement":
                _walk_statements(stmt.alternate.body, tainted_vars, add, script_base_line, script_body, html)
            else:
                _process_statement(stmt.alternate, tainted_vars, add, script_base_line, script_body, html)

    elif stmt_type in ("ForStatement", "WhileStatement", "DoWhileStatement", "ForInStatement", "ForOfStatement"):
        body = stmt.body
        if body:
            if body.type == "BlockStatement":
                _walk_statements(body.body, tainted_vars, add, script_base_line, script_body, html)
            else:
                _process_statement(body, tainted_vars, add, script_base_line, script_body, html)

    elif stmt_type == "BlockStatement":
        _walk_statements(stmt.body, tainted_vars, add, script_base_line, script_body, html)

    elif stmt_type == "TryStatement":
        if stmt.block and stmt.block.body:
            _walk_statements(stmt.block.body, tainted_vars, add, script_base_line, script_body, html)
        if stmt.handler and stmt.handler.body and stmt.handler.body.body:
            _walk_statements(stmt.handler.body.body, tainted_vars, add, script_base_line, script_body, html)

    elif stmt_type == "ReturnStatement":
        pass  # 扁平作用域下不追踪返回值


def _handle_assignment(
    expr: Any,
    tainted_vars: dict[str, TaintInfo],
    add: Callable,
    script_base_line: int,
    script_body: str,
) -> None:
    lhs = expr.left
    rhs_taint = _eval_taint(expr.right, tainted_vars) # 判断右侧是否带污点

    # 检查 LHS 是否为 Sink
    sink_label = _get_sink_label(lhs) # 判断左侧是否危险 Sink
    if sink_label is not None and rhs_taint is not None:
        _emit_finding(
            add, script_base_line, script_body,
            rhs_taint.source, rhs_taint.path, sink_label,
            expr,
        ) # Source 流入 Sink
        return

    # LHS 为简单标识符且 RHS 污点 → 更新 tainted_vars
    if lhs.type == "Identifier" and rhs_taint is not None:
        tainted_vars[lhs.name] = TaintInfo(
            source=rhs_taint.source,
            path=rhs_taint.path + [lhs.name],
        )


def _check_call_sink(
    call_node: Any,
    tainted_vars: dict[str, TaintInfo],
    add: Callable,
    script_base_line: int,
    script_body: str,
) -> None:
    if call_node.type != "CallExpression":
        return
    callee = call_node.callee
    args = call_node.arguments or []

    # 全局函数调用: eval(x), setTimeout(x), document.write(x)
    if callee.type == "Identifier":
        key = (None, callee.name)
        if key in _SINK_CALLS and args:
            taint = _eval_taint(args[0], tainted_vars) # 检查调用参数污点
            if taint is not None:
                _emit_finding(
                    add, script_base_line, script_body,
                    taint.source, taint.path, callee.name,
                    call_node,
                ) # 污点进入函数型 Sink

    elif callee.type == "MemberExpression":
        method_name = _get_prop_name(callee)
        obj_name = _get_object_name(callee)

        # document.write(x) 等
        if method_name and obj_name:
            key = (obj_name, method_name)
            if key in _SINK_CALLS and args:
                taint = _eval_taint(args[0], tainted_vars) # 检查 document.write 参数
                if taint is not None:
                    _emit_finding(
                        add, script_base_line, script_body,
                        taint.source, taint.path, f"{obj_name}.{method_name}",
                        call_node,
                    ) # 污点进入成员函数 Sink

        # insertAdjacentHTML(pos, x), jQuery .html(x)
        if method_name in _SINK_METHOD_CALLS and args:
            # insertAdjacentHTML 的第二个参数是内容
            target_arg = args[1] if method_name == "insertAdjacentHTML" and len(args) > 1 else args[0]
            taint = _eval_taint(target_arg, tainted_vars) # 检查 HTML 写入参数
            if taint is not None:
                sink_label = _SINK_METHOD_CALLS[method_name]
                _emit_finding(
                    add, script_base_line, script_body,
                    taint.source, taint.path, sink_label,
                    call_node,
                ) # 污点进入 DOM 写入 Sink


# ---------------------------------------------------------------------------
# 递归污点评估器
# ---------------------------------------------------------------------------

def _eval_taint(node: Any, tainted_vars: dict[str, TaintInfo]) -> TaintInfo | None:
    """递归评估 AST 节点的污点状态。返回 TaintInfo 或 None。"""
    if node is None:
        return None

    node_type = node.type

    # 标识符: 查 tainted_vars
    if node_type == "Identifier":
        return tainted_vars.get(node.name)

    # 字面量: 不污点
    if node_type == "Literal":
        return None

    # 成员表达式: 检查是否为污点源，否则递归评估 object
    if node_type == "MemberExpression":
        source_label = _is_source_node(node)
        if source_label:
            return TaintInfo(source=source_label)
        return _eval_taint(node.object, tainted_vars)

    # 函数调用: 检查传播规则
    if node_type == "CallExpression":
        return _eval_call_taint(node, tainted_vars)

    # new 表达式: 构造器传播
    if node_type == "NewExpression":
        return _eval_new_taint(node, tainted_vars)

    # 赋值表达式: 评估右侧
    if node_type == "AssignmentExpression":
        return _eval_taint(node.right, tainted_vars)

    # 逻辑表达式: 两侧任一污点则污点
    if node_type == "LogicalExpression":
        left = _eval_taint(node.left, tainted_vars)
        if left:
            return left
        return _eval_taint(node.right, tainted_vars)

    # 条件表达式: 两个分支任一污点则污点
    if node_type == "ConditionalExpression":
        cons = _eval_taint(node.consequent, tainted_vars)
        if cons:
            return cons
        return _eval_taint(node.alternate, tainted_vars)

    # 模板字符串: 任一表达式污点则污点
    if node_type == "TemplateLiteral":
        for expr in (node.expressions or []):
            taint = _eval_taint(expr, tainted_vars)
            if taint:
                return taint
        return None

    # 二元表达式 (+): 字符串拼接，任一侧污点则污点
    if node_type == "BinaryExpression":
        if node.operator == "+":
            left = _eval_taint(node.left, tainted_vars)
            if left:
                return left
            return _eval_taint(node.right, tainted_vars)
        return None

    # 一元表达式: 评估参数
    if node_type == "UnaryExpression":
        return _eval_taint(node.argument, tainted_vars)

    # 序列表达式: 最后一个表达式的值
    if node_type == "SequenceExpression":
        last = None
        for expr in (node.expressions or []):
            last = _eval_taint(expr, tainted_vars)
        return last

    # 展开元素: 评估参数
    if node_type == "SpreadElement":
        return _eval_taint(node.argument, tainted_vars)

    return None


def _eval_call_taint(node: Any, tainted_vars: dict[str, TaintInfo]) -> TaintInfo | None:
    """评估 CallExpression 的污点传播。"""
    callee = node.callee
    args = node.arguments or []

    # 规则 B: 污点对象的方法调用传播
    if callee.type == "MemberExpression":
        obj_taint = _eval_taint(callee.object, tainted_vars)
        if obj_taint is not None:
            method_name = _get_prop_name(callee)
            if method_name and method_name in _PROPAGATING_METHODS:
                return TaintInfo(source=obj_taint.source, path=list(obj_taint.path))

    # 规则 C: 包装函数传播 (第一个参数污点则返回值污点)
    if callee.type == "Identifier" and callee.name in _WRAPPER_FUNCTIONS and args:
        return _eval_taint(args[0], tainted_vars)

    # JSON.parse / JSON.stringify
    if callee.type == "MemberExpression":
        obj_name = _get_object_name(callee)
        method_name = _get_prop_name(callee)
        if obj_name == "JSON" and method_name in ("parse", "stringify") and args:
            return _eval_taint(args[0], tainted_vars)

    return None


def _eval_new_taint(node: Any, tainted_vars: dict[str, TaintInfo]) -> TaintInfo | None:
    """评估 NewExpression 的污点传播。"""
    callee_name = None
    if node.callee.type == "Identifier":
        callee_name = node.callee.name

    if callee_name in _TAINTED_CONSTRUCTORS:
        args = node.arguments or []
        if args:
            return _eval_taint(args[0], tainted_vars)

    return None


# ---------------------------------------------------------------------------
# 源检测
# ---------------------------------------------------------------------------

def _is_source_node(node: Any) -> str | None:
    """检查 MemberExpression 是否为污点源。返回源标签或 None。"""
    if node.type != "MemberExpression":
        return None
    if node.object.type != "Identifier":
        return None
    prop_name = _get_prop_name(node)
    if not prop_name:
        return None
    key = (node.object.name, prop_name)
    return _SOURCE_MEMBERS.get(key)


def _is_source_identifier(name: str) -> str | None:
    return _SOURCE_IDENTIFIERS.get(name)


# ---------------------------------------------------------------------------
# Sink 检测
# ---------------------------------------------------------------------------

def _get_sink_label(lhs: Any) -> str | None:
    """检查赋值 LHS 是否为 Sink，返回 Sink 标签或 None。"""
    if lhs.type == "MemberExpression":
        prop_name = _get_prop_name(lhs)
        if prop_name and prop_name in _SINK_ASSIGN_PROPS:
            return _get_member_chain(lhs)
    return None


# ---------------------------------------------------------------------------
# AST 辅助函数
# ---------------------------------------------------------------------------

def _get_prop_name(node: Any) -> str | None:
    """从 MemberExpression 提取属性名（支持 computed 和 non-computed）。"""
    if node.type != "MemberExpression":
        return None
    if node.computed:
        if node.property.type == "Literal" and isinstance(node.property.value, str):
            return node.property.value
        return None
    if node.property.type == "Identifier":
        return node.property.name
    return None


def _get_object_name(node: Any) -> str | None:
    """从 MemberExpression 提取对象名（简单 Identifier 情况）。"""
    if node.type != "MemberExpression":
        return None
    if node.object.type == "Identifier":
        return node.object.name
    return None


def _get_member_chain(node: Any) -> str:
    """将 MemberExpression 递归转为点号链字符串。

    例: document.getElementById("output").innerHTML
        → "document.getElementById().innerHTML"
    """
    parts: list[str] = []
    _collect_chain(node, parts)
    return "".join(parts)


def _collect_chain(node: Any, parts: list[str]) -> None:
    if node.type == "MemberExpression":
        _collect_chain(node.object, parts)
        prop = _get_prop_name(node)
        if prop:
            parts.append(f".{prop}")
        else:
            parts.append("[]")
    elif node.type == "CallExpression":
        _collect_chain(node.callee, parts)
        parts.append("()")
    elif node.type == "Identifier":
        parts.append(node.name)
    else:
        parts.append("?")


# ---------------------------------------------------------------------------
# 证据输出
# ---------------------------------------------------------------------------

def _emit_finding(
    add: Callable,
    script_base_line: int,
    script_body: str,
    source: str,
    path: list[str],
    sink: str,
    node: Any,
) -> None:
    flow_display = _build_flow_display(source, path, sink) # 拼接 Source -> Sink 链路
    line = script_base_line + (getattr(node, "loc", None) and node.loc.start.line or 1) - 1
    snippet = _extract_snippet(script_body, node) # 截取证据代码
    add(
        "ast_data_flow",
        "high",
        "Script data flow to dangerous sink",
        snippet,
        line,
        flow_display,
        {
            "source": source,
            "path": path,
            "sink": sink,
            "flow_display": flow_display,
        },
    ) # 写入静态发现列表


def _build_flow_display(source: str, path: list[str], sink: str) -> str:
    chain = [source] + [p for p in path if p] + [sink]
    return " -> ".join(chain)


def _extract_snippet(script_body: str, node: Any) -> str:
    try:
        r = node.range
        snippet = script_body[r[0]:r[1]]
    except Exception:
        snippet = str(node.type)
    snippet = re.sub(r"\s+", " ", snippet.strip())
    return snippet[:500]
