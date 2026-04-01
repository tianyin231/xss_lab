# 加工公共方法，没有也能跑程序
try:
    from OneSightPublic.settings import *  # type: ignore
except Exception:
    pass

# ============================================================
# XSSLab - 全局配置
# ============================================================

# ------------------------------------------------------------
# 系统基础配置
# ------------------------------------------------------------
SYSTEM_NAME = "XSSLab"
SYSTEM_VERSION = "0.1.0"

LOG_DIR = "logs"
LOG_LEVEL = "INFO"
LOG_FILE_ENCODING = "utf-8"
LOG_SPLIT_MODE = "by_run"
LOG_CONSOLE_VERBOSE = True

REPORT_DIR = "reports"
REPORT_FORMAT = "json"
REPORT_FAILED_ONLY = False
REPORT_SPLIT_MODE = "by_run"

# ------------------------------------------------------------
# Web / API 配置
# ------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 5001
FLASK_DEBUG = True
CORS_ORIGINS = "*"

# ------------------------------------------------------------
# 数据库配置（优先 DATABASE_URL；否则使用 MYSQL_* 组装）
# ------------------------------------------------------------
DATABASE_URL = ""
# DATABASE_URL = "sqlite:////Users/chen/PycharmProjects/xss/dev.db"
DATABASE_URL = "sqlite:///dev.db"
# DATABASE_URL = "mysql+pymysql://root:pass@127.0.0.1:3306/server?charset=utf8mb4"
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DATABASE = "server"

MYSQL_POOL_SIZE = 10
MYSQL_MAX_OVERFLOW = 20

# ------------------------------------------------------------
# 爬虫 / 扫描配置
# ------------------------------------------------------------
CRAWLER_USER_AGENT = "server-crawler/0.1"
SCRAPY_HTTPCACHE_DIR = ".httpcache"

CRAWLER_ROBOTSTXT_OBEY = True
CRAWLER_CONCURRENT_REQUESTS = 16
CRAWLER_CONCURRENT_REQUESTS_PER_DOMAIN = 8
CRAWLER_DOWNLOAD_TIMEOUT = 20
CRAWLER_RETRY_TIMES = 2

MAX_DEPTH_DEFAULT = 2
MAX_PAGES_DEFAULT = 200

USE_SELENIUM_DEFAULT = False