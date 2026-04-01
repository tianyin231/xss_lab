"""
Scrapy 爬虫逻辑模块
作用：定义深度爬取策略、链接提取规则，并调用分析引擎对页面内容进行 XSS 风险审计。
"""
from __future__ import annotations

import gzip
import zlib
import hashlib
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import scrapy
from scrapy.exceptions import CloseSpider
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Spider

from server.analyzer import analyze_html
from server.worker_context import get_stop_requested, push_event


class DeepSpider(Spider):
    name = "deep_spider"

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "COOKIES_ENABLED": False,
        "TELNETCONSOLE_ENABLED": False,
        "LOG_ENABLED": True,
        "LOG_LEVEL": "DEBUG",
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.25,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
        "CONCURRENT_REQUESTS": 16,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 2,
        "DOWNLOAD_TIMEOUT": 20,
        "HTTPCACHE_ENABLED": True,
        "HTTPCACHE_IGNORE_HTTP_CODES": [301, 302, 303, 307, 308],
    }

    def __init__(
        self,
        target_url: str,
        max_depth: int,
        max_pages: int,
        use_selenium: bool,
        job_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.job_id = job_id
        self.target_url = target_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.use_selenium = use_selenium
        parsed = urlparse(target_url)
        self.allowed_domains = [parsed.hostname] if parsed.hostname else []
        self.start_urls = [target_url]

        self._pages_seen = 0
        self._link_extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny_extensions=(),
            unique=True,
        )

    def start_requests(self) -> Iterable[scrapy.Request]:
        push_event(self.job_id, "log", {"message": f"start: {self.target_url}"})
        yield scrapy.Request(self.target_url, callback=self.parse, dont_filter=True, meta={"depth": 0})

    def parse(self, response: scrapy.http.Response, **kwargs: Any) -> Iterable[Any]:
        if get_stop_requested():
            push_event(self.job_id, "log", {"message": "stopping crawler engine..."})
            raise CloseSpider("user_requested_stop")

        self._pages_seen += 1
        content_type = (response.headers.get("Content-Type") or b"").decode("utf-8", "ignore")
        body = response.body or b""
        sha256 = hashlib.sha256(body).hexdigest()

        push_event(
            self.job_id,
            "page",
            {
                "url": response.url,
                "status_code": int(getattr(response, "status", 0) or 0),
                "content_type": content_type,
                "sha256": sha256,
            },
        )

        is_html = "text/html" in content_type.lower()
        if is_html:
            text = _safe_decode(response)
            findings_count = 0
            for f in analyze_html(text):
                findings_count += 1
                push_event(
                    self.job_id,
                    "finding",
                    {
                        "url": response.url,
                        "kind": f.kind,
                        "severity": f.severity,
                        "title": f.title,
                        "evidence": f.evidence,
                    },
                )
            if findings_count > 0:
                push_event(self.job_id, "log", {"message": f"分析完成: {response.url}, 发现 {findings_count} 个潜在风险点"})
        else:
            push_event(self.job_id, "log", {"message": f"跳过分析 (非 HTML): {response.url} ({content_type})"})

        if self._pages_seen >= self.max_pages:
            push_event(self.job_id, "log", {"message": f"max_pages reached: {self.max_pages}"})
            return

        depth = int(response.meta.get("depth", 0))
        if depth >= self.max_depth:
            return

        links = self._link_extractor.extract_links(response)
        for link in links:
            if get_stop_requested():
                return
            if not _is_http_url(link.url):
                continue
            yield scrapy.Request(
                link.url,
                callback=self.parse,
                dont_filter=False,
                meta={"depth": depth + 1},
            )


_HTTP_RE = re.compile(r"^https?://", re.IGNORECASE)


def _is_http_url(url: str) -> bool:
    return bool(_HTTP_RE.match(url))


def _safe_decode(response: scrapy.http.Response) -> str:
    """尝试以最稳健的方式解码响应体，处理可能的压缩和编码问题"""
    body = response.body
    
    # 1. 处理常见的压缩格式
    encoding = response.headers.get("Content-Encoding", b"").lower()
    try:
        if encoding == b"gzip":
            body = gzip.decompress(body)
        elif encoding == b"deflate":
            body = zlib.decompress(body)
        elif encoding == b"br":
            try:
                import brotli
                body = brotli.decompress(body)
            except ImportError:
                pass
    except Exception:
        pass

    # 2. 尝试使用 response 自带的 text 属性（Scrapy 会自动处理编码）
    try:
        return response.text
    except Exception:
        pass

    # 3. 兜底方案：尝试 utf-8 或 latin-1
    for enc in ["utf-8", "gbk", "latin-1"]:
        try:
            return body.decode(enc)
        except Exception:
            continue
            
    return ""
