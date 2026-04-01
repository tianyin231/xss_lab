"""
爬虫工作进程模块
作用：Scrapy 运行的独立进程入口，包含日志捕获扩展和 Selenium 动态渲染中间件。
"""
from __future__ import annotations

import multiprocessing as mp
import os
import importlib
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from scrapy import signals
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings

from server.spider import DeepSpider
from server.worker_context import init_worker, push_event, get_stop_requested


from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions


class SeleniumMiddleware:
    """Scrapy 中间件：使用 Selenium 渲染页面"""

    def __init__(self, timeout=20):
        self.timeout = timeout
        self.driver = None

    def _init_driver(self):
        if self.driver:
            return
        
        # 尝试初始化 Chrome (Headless)
        try:
            opts = ChromeOptions()
            opts.add_argument("--headless")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            self.driver = webdriver.Chrome(options=opts)
            self.driver.set_page_load_timeout(self.timeout)
            return
        except Exception:
            pass

        # 尝试初始化 Firefox (Headless)
        try:
            opts = FirefoxOptions()
            opts.add_argument("--headless")
            self.driver = webdriver.Firefox(options=opts)
            self.driver.set_page_load_timeout(self.timeout)
            return
        except Exception:
            pass
        
        raise RuntimeError("无法启动 Selenium 浏览器 (请确保已安装 Chrome 或 Firefox 及其驱动)")

    def process_request(self, request, spider):
        if not getattr(spider, "use_selenium", False):
            return None

        try:
            self._init_driver()
            spider.logger.debug(f"Selenium 正在渲染: {request.url}")
            self.driver.get(request.url)
            # 等待一段固定时间确保脚本执行（实际生产中可使用 WebDriverWait）
            time.sleep(2)
            body = self.driver.page_source
            return HtmlResponse(
                self.driver.current_url,
                body=body,
                encoding="utf-8",
                request=request
            )
        except Exception as e:
            spider.logger.error(f"Selenium 渲染失败: {e}")
            return None

    def __del__(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


class LogPushExtension:
    """Scrapy 扩展：捕获 Scrapy 日志并推送到前端"""

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        # 设置 logging handler
        handler = LogPushHandler(crawler.spider)
        logging.getLogger().addHandler(handler)
        
        # 启动停止监控线程
        t = threading.Thread(target=ext._stop_monitor, args=(crawler,), daemon=True)
        t.start()
        return ext

    def spider_opened(self, spider):
        pass

    def _stop_monitor(self, crawler):
        """每秒检查一次是否需要停止 Scrapy 引擎"""
        while True:
            if get_stop_requested():
                if crawler.engine and crawler.engine.running:
                    crawler.engine.stop()
                break
            time.sleep(1.0)


class LogPushExtension:
    """Scrapy 扩展：捕获 Scrapy 日志并推送到前端"""

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        return ext

    def spider_opened(self, spider):
        # 在爬虫打开时设置日志处理器
        handler = LogPushHandler(spider)
        logging.getLogger().addHandler(handler)


class LogPushHandler(logging.Handler):
    """自定义 Logging Handler"""

    def __init__(self, spider):
        super().__init__()
        self.spider = spider

    def emit(self, record):
        try:
            msg = self.format(record)
            if hasattr(self.spider, "job_id"):
                push_event(self.spider.job_id, "log", {"message": msg})
        except Exception:
            pass


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    target_url: str
    max_depth: int
    max_pages: int
    use_selenium: bool


def run_worker(job: JobSpec, out_queue: mp.Queue, stop_event: mp.Event) -> None:
    init_worker(out_queue=out_queue, stop_event=stop_event)
    push_event(job.job_id, "log", {"message": "worker started"})

    app_settings = _settings_module()
    settings = Settings()
    cache_dir = _get(app_settings, "SCRAPY_HTTPCACHE_DIR", os.getenv("SCRAPY_HTTPCACHE_DIR", ".httpcache"))
    settings.set("HTTPCACHE_DIR", cache_dir, priority="project")
    settings.set(
        "USER_AGENT",
        _get(app_settings, "CRAWLER_USER_AGENT", os.getenv("CRAWLER_USER_AGENT", "server-crawler/0.1")),
        priority="project",
    )

    settings.set(
        "ROBOTSTXT_OBEY",
        _get_bool(app_settings, "CRAWLER_ROBOTSTXT_OBEY", bool(int(os.getenv("CRAWLER_ROBOTSTXT_OBEY", "1")))),
        priority="project",
    )
    settings.set(
        "CONCURRENT_REQUESTS",
        _get_int(app_settings, "CRAWLER_CONCURRENT_REQUESTS", int(os.getenv("CRAWLER_CONCURRENT_REQUESTS", "16"))),
        priority="project",
    )
    settings.set(
        "CONCURRENT_REQUESTS_PER_DOMAIN",
        _get_int(
            app_settings,
            "CRAWLER_CONCURRENT_REQUESTS_PER_DOMAIN",
            int(os.getenv("CRAWLER_CONCURRENT_REQUESTS_PER_DOMAIN", "8")),
        ),
        priority="project",
    )
    settings.set(
        "DOWNLOAD_TIMEOUT",
        _get_int(app_settings, "CRAWLER_DOWNLOAD_TIMEOUT", int(os.getenv("CRAWLER_DOWNLOAD_TIMEOUT", "20"))),
        priority="project",
    )
    settings.set(
        "RETRY_TIMES",
        _get_int(app_settings, "CRAWLER_RETRY_TIMES", int(os.getenv("CRAWLER_RETRY_TIMES", "2"))),
        priority="project",
    )

    # 启用自定义 Log Handler 将 Scrapy 日志推送到前端
    settings.set("LOG_ENABLED", True, priority="project")
    settings.set("LOG_LEVEL", "DEBUG", priority="project")
    settings.set(
        "EXTENSIONS",
        {"server.worker.LogPushExtension": 100},
        priority="project",
    )
    settings.set(
        "DOWNLOADER_MIDDLEWARES",
        {"server.worker.SeleniumMiddleware": 800},
        priority="project",
    )

    process = CrawlerProcess(settings=settings)
    process.crawl(
        DeepSpider,
        target_url=job.target_url,
        max_depth=job.max_depth,
        max_pages=job.max_pages,
        use_selenium=job.use_selenium,
        job_id=job.job_id,
    )
    try:
        process.start(stop_after_crawl=True)
        push_event(job.job_id, "done", {})
    except Exception as e:
        push_event(job.job_id, "error", {"message": str(e)})


def parse_job_spec(payload: dict[str, Any]) -> JobSpec:
    return JobSpec(
        job_id=str(payload["job_id"]),
        target_url=str(payload["target_url"]),
        max_depth=int(payload["max_depth"]),
        max_pages=int(payload["max_pages"]),
        use_selenium=bool(payload.get("use_selenium", False)),
    )


def _settings_module() -> Any | None:
    try:
        return importlib.import_module("settings")
    except Exception:
        return None


def _get(mod: Any | None, name: str, default: Any) -> Any:
    if name in os.environ:
        return os.environ[name]
    if mod is not None and hasattr(mod, name):
        return getattr(mod, name)
    return default


def _get_int(mod: Any | None, name: str, default: int) -> int:
    v = _get(mod, name, None)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default


def _get_bool(mod: Any | None, name: str, default: bool) -> bool:
    v = _get(mod, name, None)
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default
