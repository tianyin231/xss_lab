"""AI 接口封装。"""
from __future__ import annotations

import json
import httpx
from typing import Any, Dict, Optional

from app_config import get, get_bool, get_float, get_int


class AIModelAPI:
    """兼容 OpenAI 风格接口的 AI 客户端。"""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.enabled = get_bool("AI_ENABLED", True)
        self.model = model or str(get("AI_MODEL", "deepseek-chat"))
        self.api_key = api_key or str(get("AI_API_KEY", ""))
        self.base_url = (base_url or str(get("AI_BASE_URL", "https://api.deepseek.com/v1"))).rstrip("/")
        self.timeout = get_float("AI_TIMEOUT", 60.0)
        self.temperature = get_float("AI_TEMPERATURE", 0.3)
        self.max_tokens = get_int("AI_MAX_TOKENS", 2000)

    def analyze_xss_result(self, html: str, test_result: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI analysis is disabled")
        if not self.api_key:
            raise RuntimeError("AI_API_KEY is not configured")

        prompt = self._build_analysis_prompt(html, test_result)
        return self._call_chat_completions(prompt)

    def _build_analysis_prompt(self, html: str, test_result: Dict[str, Any]) -> str:
        snippet = html[:4000] if html else ""
        return (
            "你是一位网络安全专家，负责复核 XSS 扫描结果。\n\n"
            "请基于页面 HTML 和扫描发现，输出简洁但具体的分析报告，至少包含：\n"
            "1. 总结\n"
            "2. 测试准确性判断\n"
            "3. 可能的误报或漏报\n"
            "4. 风险评估\n"
            "5. 修复或改进建议\n\n"
            f"HTML 片段:\n{snippet}\n\n"
            f"扫描结果:\n{json.dumps(test_result, ensure_ascii=False, indent=2)}"
        )

    def _call_chat_completions(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一位网络安全专家，精通 XSS 漏洞分析。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        response.raise_for_status()
        api_response = response.json()
        content = api_response["choices"][0]["message"]["content"]

        return {
            "success": True,
            "analysis": {
                "summary": content[:500] + "..." if len(content) > 500 else content,
                "accuracy": "",
                "false_positives": [],
                "false_negatives": [],
                "suggestions": [],
                "risk_assessment": "",
                "full_report": content,
            },
        }


def get_ai_analyzer(model: Optional[str] = None) -> AIModelAPI:
    return AIModelAPI(model)
