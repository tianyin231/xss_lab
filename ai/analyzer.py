"""AI 分析器封装。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app_config import get
from ai.api import get_ai_analyzer


class AIAnalyzer:
    """对 AI API 做一层轻量包装。"""

    def __init__(self, model: Optional[str] = None):
        self.ai_client = get_ai_analyzer(model or str(get("AI_MODEL", "deepseek-chat")))

    def analyze_xss_result(self, html: str, test_result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.ai_client.analyze_xss_result(html, test_result)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "analysis": None
            }

    def analyze_html(self, html: str) -> Dict[str, Any]:
        test_result = {"status": "pending", "payloads": []}
        return self.analyze_xss_result(html, test_result)

    def explain_workbench(self, page_context: Dict[str, Any], report_context: Dict[str, Any], audience: str = "developer") -> Dict[str, Any]:
        try:
            return self.ai_client.explain_workbench(page_context, report_context, audience)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "explanation": None,
            }


def get_analyzer(model: Optional[str] = None) -> AIAnalyzer:
    return AIAnalyzer(model)
