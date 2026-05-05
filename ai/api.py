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

    def explain_workbench(
        self,
        page_context: Dict[str, Any],
        report_context: Dict[str, Any],
        audience: str = "developer",
    ) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI analysis is disabled")
        if not self.api_key:
            raise RuntimeError("AI_API_KEY is not configured")

        prompt = self._build_workbench_explanation_prompt(page_context, report_context, audience)
        result = self._call_chat(prompt, system_content="你是一位擅长解释 XSS 验证结果的安全讲解员。")
        return {
            "success": True,
            "explanation": {
                "audience": audience,
                "content": result,
                "summary": result[:500] + "..." if len(result) > 500 else result,
            },
        }

    def recommend_validation_plan(
        self,
        page_context: Dict[str, Any],
        candidates: list[Dict[str, Any]],
        mode: str = "standard",
    ) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI analysis is disabled")
        if not self.api_key:
            raise RuntimeError("AI_API_KEY is not configured")

        prompt = self._build_validation_plan_prompt(page_context, candidates, mode)
        result = self._call_chat(prompt, system_content="你是一位擅长设计安全验证策略的 XSS 分析助手。")
        return {
            "success": True,
            "plan": {
                "mode": mode,
                "content": result,
                "summary": result[:500] + "..." if len(result) > 500 else result,
            },
        }

    def generate_payloads(
        self,
        finding_context: Dict[str, Any],
        page_html: str,
        mode: str = "exploit",
    ) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("AI analysis is disabled")
        if not self.api_key:
            raise RuntimeError("AI_API_KEY is not configured")

        prompt = self._build_payload_generation_prompt(finding_context, page_html, mode)
        result = self._call_chat(
            prompt,
            system_content="你是一位精通 XSS 漏洞利用与防御的安全专家，擅长根据页面上下文生成精准的验证 Payload。",
        )
        return {
            "success": True,
            "payloads": {
                "mode": mode,
                "content": result,
                "summary": result[:500] + "..." if len(result) > 500 else result,
            },
        }

    def _build_payload_generation_prompt(
        self,
        finding_context: Dict[str, Any],
        page_html: str,
        mode: str,
    ) -> str:
        snippet_html = page_html[:3000] if page_html else ""

        mode_instruction = {
            "probe": (
                "你必须只生成非执行型的安全探针 payload，例如独特的标记字符串（如 xsslab_ai_probe_<random>）。"
                "不要生成任何可执行的标签、事件处理器或脚本。目标是确认输入链路是否存在，而不是触发执行。"
            ),
            "exploit": (
                "你可以生成真实的 XSS 利用 payload，包括标签注入、属性逃逸、JavaScript 字符串闭合、"
                "协议注入等。目标是尽可能触发可观察的执行或回显信号。"
            ),
        }.get(mode, "请根据上下文生成合适的验证 payload。")

        finding_json = json.dumps(finding_context, ensure_ascii=False, indent=2)

        return (
            "你需要为一个 XSS 漏洞扫描工具生成验证 Payload。\n\n"
            f"【模式要求】\n{mode_instruction}\n\n"
            "【漏洞上下文】\n"
            f"{finding_json}\n\n"
            "【页面 HTML 片段】\n"
            f"{snippet_html}\n\n"
            "【输出要求】\n"
            "1. 输出严格 JSON，格式：\n"
            '{"payloads":[{"payload":"具体payload","vector":"query或form或hash",'
            '"context":"script或html_text或html_attr","reason":"为什么这个payload应该有效"}]}\n'
            "2. 最多生成 5 个 payload，按优先级从高到低排列\n"
            "3. 每个 payload 必须结合具体漏洞上下文（source、sink、flow_display）来设计\n"
            "4. vector 必须从 query/form/hash 中选择，基于漏洞的数据流路径判断\n"
            "5. context 必须从 script/html_text/html_attr 中选择，基于 sink 类型判断\n"
            "6. reason 必须具体说明为什么这个 payload 针对当前漏洞上下文有效\n"
            "7. 不要输出 JSON 以外的任何内容"
        )

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

    def _build_workbench_explanation_prompt(
        self,
        page_context: Dict[str, Any],
        report_context: Dict[str, Any],
        audience: str,
    ) -> str:
        audience_hint = {
            "beginner": "请用更通俗、教学化的语言解释，尽量减少术语堆叠。",
            "developer": "请用开发者能快速理解的语言解释，强调输入、回显、上下文和修复重点。",
            "thesis": "请用适合论文或答辩展示的语言解释，强调结论、依据和意义。",
        }.get(audience, "请用清晰、专业但易懂的语言解释。")
        return (
            "你正在解释一个 XSS 页面验证工作台中的当前结果。\n\n"
            f"{audience_hint}\n\n"
            "输出要求：\n"
            "1. 先给出一句总判断\n"
            "2. 再解释为什么会得到这个复测结果\n"
            "3. 如果有对比报告，说明两次结果最大的变化点\n"
            "4. 最后给出下一步建议\n"
            "5. 不要空泛，要结合给定页面、向量、参数、回显和上下文\n\n"
            f"页面上下文:\n{json.dumps(page_context, ensure_ascii=False, indent=2)}\n\n"
            f"复测上下文:\n{json.dumps(report_context, ensure_ascii=False, indent=2)}"
        )

    def _build_validation_plan_prompt(
        self,
        page_context: Dict[str, Any],
        candidates: list[Dict[str, Any]],
        mode: str,
    ) -> str:
        return (
            "你需要为一个页面验证工作台推荐安全的多轮验证计划。\n\n"
            "要求：\n"
            "1. 只能选择非执行型、低风险的验证探针\n"
            "2. 优先提高判断准确率，而不是追求攻击利用\n"
            "3. 输出 JSON，格式必须是："
            '{"reason":"总理由","rounds":[{"candidate_id":"候选ID","reason":"选择理由"}]}\n'
            "4. quick 模式最多 2 轮，standard 最多 3 轮，deep 最多 5 轮\n"
            "5. 如果有 form/query/hash 等不同向量，优先给出更值得先测的顺序\n\n"
            f"模式：{mode}\n\n"
            f"页面上下文：\n{json.dumps(page_context, ensure_ascii=False, indent=2)}\n\n"
            f"候选探针：\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
        )

    def _call_chat_completions(self, prompt: str) -> Dict[str, Any]:
        content = self._call_chat(prompt, system_content="你是一位网络安全专家，精通 XSS 漏洞分析。")
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

    def _call_chat(self, prompt: str, system_content: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
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
        return api_response["choices"][0]["message"]["content"]


def get_ai_analyzer(model: Optional[str] = None) -> AIModelAPI:
    return AIModelAPI(model)
