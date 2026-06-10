"""AI 分析器封装。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app_config import get
from ai.api import get_ai_analyzer


class AIAnalyzer:
    """对 AI API 做一层轻量包装。"""

    def __init__(self, model: Optional[str] = None):
        self.ai_client = get_ai_analyzer(model or str(get("AI_MODEL", "deepseek-chat"))) # 创建 AI 客户端

    def analyze_xss_result(self, html: str, test_result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.ai_client.analyze_xss_result(html, test_result) # 分析扫描结果
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "analysis": None
            }

    def analyze_html(self, html: str) -> Dict[str, Any]:
        test_result = {"status": "pending", "payloads": []}
        return self.analyze_xss_result(html, test_result) # 兼容简单 HTML 分析

    def explain_workbench(self, page_context: Dict[str, Any], report_context: Dict[str, Any], audience: str = "developer") -> Dict[str, Any]:
        try:
            return self.ai_client.explain_workbench(page_context, report_context, audience) # 生成页面解释
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "explanation": None,
            }

    def recommend_validation_plan(self, page_context: Dict[str, Any], candidates: list[Dict[str, Any]], mode: str = "standard") -> Dict[str, Any]:
        try:
            return self.ai_client.recommend_validation_plan(page_context, candidates, mode) # 推荐验证轮次
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "plan": None,
            }

    def generate_payloads(self, finding_context: Dict[str, Any], page_html: str, mode: str = "exploit") -> Dict[str, Any]:
        try:
            return self.ai_client.generate_payloads(finding_context, page_html, mode) # 生成候选 payload
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "payloads": None,
            }


def get_analyzer(model: Optional[str] = None) -> AIAnalyzer:
    return AIAnalyzer(model) # API 层统一从这里获取分析器
