"""
AI大模型API调用模块
作用：封装大模型API调用逻辑，支持多种大模型服务
"""
from __future__ import annotations

import os
import json
import httpx
from typing import Any, Dict, Optional, List


class AIModelAPI:
    """AI大模型API客户端"""
    
    def __init__(self, model: str = "deepseek-chat", api_key: Optional[str] = None, base_url: Optional[str] = None):
        """初始化AI模型API客户端
        
        Args:
            model: 模型名称
            api_key: API密钥
            base_url: API基础URL
        """
        self.model = model
        self.api_key = api_key or "sk-130bf79101914f0cac13672bba65ad0b"  # 使用用户提供的DeepSeek API密钥
        self.base_url = base_url or self._get_default_base_url(model)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _get_default_base_url(self, model: str) -> str:
        """获取默认的API基础URL
        
        Args:
            model: 模型名称
            
        Returns:
            str: API基础URL
        """
        if model.startswith("deepseek-"):
            return "https://api.deepseek.com/v1"
        elif model.startswith("gpt-"):
            return "https://api.openai.com/v1"
        elif model.startswith("claude-"):
            return "https://api.anthropic.com/v1"
        else:
            return "https://api.deepseek.com/v1"  # 默认使用DeepSeek API
    
    def analyze_xss_result(self, html: str, test_result: Dict[str, Any]) -> Dict[str, Any]:
        """分析XSS测试结果
        
        Args:
            html: HTML内容
            test_result: 测试结果
            
        Returns:
            Dict[str, Any]: AI分析结果
        """
        prompt = self._build_analysis_prompt(html, test_result)
        
        if self.model.startswith("deepseek-"):
            return self._call_deepseek(prompt)
        elif self.model.startswith("gpt-"):
            return self._call_openai(prompt)
        elif self.model.startswith("claude-"):
            return self._call_anthropic(prompt)
        else:
            return self._call_deepseek(prompt)  # 默认使用DeepSeek
    
    def _build_analysis_prompt(self, html: str, test_result: Dict[str, Any]) -> str:
        """构建分析提示
        
        Args:
            html: HTML内容
            test_result: 测试结果
            
        Returns:
            str: 提示内容
        """
        return f"""你是一位网络安全专家，负责分析XSS测试结果。

请分析以下HTML内容和测试结果，判断测试结果是否准确，并给出详细的分析报告。

HTML内容：
{html[:2000]}...

测试结果：
{json.dumps(test_result, indent=2)}

分析要求：
1. 评估测试结果的准确性
2. 分析可能的误报或漏报
3. 提供改进测试的建议
4. 给出安全风险评估
5. 生成一份结构化的分析报告
"""
    
    def _call_deepseek(self, prompt: str) -> Dict[str, Any]:
        """调用DeepSeek API
        
        Args:
            prompt: 提示内容
            
        Returns:
            Dict[str, Any]: API响应
        """
        import traceback
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一位网络安全专家，精通XSS漏洞分析。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            }
            
            print(f"调用DeepSeek API: {self.base_url}/chat/completions")
            print(f"请求头: {self.headers}")
            print(f"请求体大小: {len(str(payload))} 字符")
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text[:500]}...")
            
            response.raise_for_status()
            api_response = response.json()
            
            # 处理API响应，转换为统一格式
            return {
                "success": True,
                "analysis": {
                    "summary": api_response["choices"][0]["message"]["content"][:500] + "..." if len(api_response["choices"][0]["message"]["content"]) > 500 else api_response["choices"][0]["message"]["content"],
                    "accuracy": "",
                    "false_positives": [],
                    "false_negatives": [],
                    "suggestions": [],
                    "risk_assessment": "",
                    "full_report": api_response["choices"][0]["message"]["content"]
                }
            }
        except Exception as e:
            print(f"DeepSeek API调用失败: {e}")
            traceback.print_exc()
            raise
    
    def _call_openai(self, prompt: str) -> Dict[str, Any]:
        """调用OpenAI API
        
        Args:
            prompt: 提示内容
            
        Returns:
            Dict[str, Any]: API响应
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一位网络安全专家，精通XSS漏洞分析。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            
        response.raise_for_status()
        api_response = response.json()
        
        return {
            "success": True,
            "analysis": {
                "summary": api_response["choices"][0]["message"]["content"][:500] + "..." if len(api_response["choices"][0]["message"]["content"]) > 500 else api_response["choices"][0]["message"]["content"],
                "accuracy": "",
                "false_positives": [],
                "false_negatives": [],
                "suggestions": [],
                "risk_assessment": "",
                "full_report": api_response["choices"][0]["message"]["content"]
            }
        }
    
    def _call_anthropic(self, prompt: str) -> Dict[str, Any]:
        """调用Anthropic API
        
        Args:
            prompt: 提示内容
            
        Returns:
            Dict[str, Any]: API响应
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens_to_sample": 2000,
            "temperature": 0.3
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/completions",
                headers=self.headers,
                json=payload
            )
            
        response.raise_for_status()
        api_response = response.json()
        
        return {
            "success": True,
            "analysis": {
                "summary": api_response["completion"][:500] + "..." if len(api_response["completion"]) > 500 else api_response["completion"],
                "accuracy": "",
                "false_positives": [],
                "false_negatives": [],
                "suggestions": [],
                "risk_assessment": "",
                "full_report": api_response["completion"]
            }
        }


def get_ai_analyzer(model: str = "deepseek-chat") -> AIModelAPI:
    """获取AI分析器实例
    
    Args:
        model: 模型名称
        
    Returns:
        AIModelAPI: AI模型API客户端实例
    """
    return AIModelAPI(model)
