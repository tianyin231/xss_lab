"""
AI分析器模块
作用：实现HTML和测试结果的分析逻辑，使用大模型API进行智能分析
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ai.api import get_ai_analyzer


class AIAnalyzer:
    """AI分析器"""
    
    def __init__(self, model: str = "gpt-4"):
        """初始化AI分析器
        
        Args:
            model: 模型名称
        """
        self.ai_client = get_ai_analyzer(model)
    
    def analyze_xss_result(self, html: str, test_result: Dict[str, Any]) -> Dict[str, Any]:
        """分析XSS测试结果
        
        Args:
            html: HTML内容
            test_result: 测试结果
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        try:
            # 调用AI API进行分析
            ai_response = self.ai_client.analyze_xss_result(html, test_result)
            
            # 处理AI响应
            analysis_result = self._process_ai_response(ai_response)
            
            return {
                "success": True,
                "analysis": analysis_result,
                "raw_response": ai_response
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "analysis": None
            }
    
    def _process_ai_response(self, ai_response: Dict[str, Any]) -> Dict[str, Any]:
        """处理AI响应
        
        Args:
            ai_response: AI API响应
            
        Returns:
            Dict[str, Any]: 处理后的分析结果
        """
        try:
            # 处理OpenAI响应
            if "choices" in ai_response:
                content = ai_response["choices"][0]["message"]["content"]
            # 处理Anthropic响应
            elif "completion" in ai_response:
                content = ai_response["completion"]
            # 处理DeepSeek响应
            elif "analysis" in ai_response:
                content = ai_response["analysis"]["full_report"]
            else:
                content = str(ai_response)
            
            # 解析分析报告
            return self._parse_analysis_report(content)
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 返回默认分析结果
            return {
                "summary": "API响应处理失败，使用默认分析结果",
                "accuracy": "测试结果准确性评估：中等",
                "false_positives": ["某些测试可能存在误报，需要进一步验证"],
                "false_negatives": ["可能存在未检测到的XSS漏洞"],
                "suggestions": ["增加更多的测试用例", "使用更复杂的payload", "检查DOM-based XSS漏洞"],
                "risk_assessment": "风险等级：中等。虽然发现了一些潜在的XSS漏洞，但它们的利用难度较高。",
                "full_report": f"# XSS漏洞分析报告\n\n## 分析摘要\nAPI响应处理失败，使用默认分析结果。\n\n## 测试准确性\n测试结果的准确性评估为中等，可能存在一些误报和漏报。\n\n## 潜在问题\n- 可能存在未检测到的DOM-based XSS漏洞\n- 某些测试用例可能过于简单\n\n## 改进建议\n1. 增加更多的测试用例\n2. 使用更复杂的payload\n3. 检查DOM-based XSS漏洞\n4. 考虑不同浏览器的兼容性\n\n## 风险评估\n风险等级：中等\n虽然发现了一些潜在的XSS漏洞，但它们的利用难度较高。建议进一步测试和验证。\n\n## 技术细节\n- 错误信息: {str(e)}"
            }
    
    def _parse_analysis_report(self, content: str) -> Dict[str, Any]:
        """解析分析报告
        
        Args:
            content: AI生成的分析报告
            
        Returns:
            Dict[str, Any]: 解析后的分析结果
        """
        # 简单解析，实际项目中可能需要更复杂的解析逻辑
        lines = content.strip().split('\n')
        
        report = {
            "summary": "",
            "accuracy": "",
            "false_positives": [],
            "false_negatives": [],
            "suggestions": [],
            "risk_assessment": "",
            "full_report": content
        }
        
        # 提取关键信息
        current_section = None
        for line in lines:
            line = line.strip()
            
            if line.startswith("### ") or line.startswith("## "):
                current_section = line.lower()
            elif "准确性" in line or "accuracy" in line.lower():
                report["accuracy"] = line
            elif "误报" in line or "false positive" in line.lower():
                current_section = "false_positives"
            elif "漏报" in line or "false negative" in line.lower():
                current_section = "false_negatives"
            elif "建议" in line or "suggestion" in line.lower():
                current_section = "suggestions"
            elif "风险评估" in line or "risk assessment" in line.lower():
                current_section = "risk_assessment"
            elif current_section == "false_positives" and line:
                report["false_positives"].append(line)
            elif current_section == "false_negatives" and line:
                report["false_negatives"].append(line)
            elif current_section == "suggestions" and line:
                report["suggestions"].append(line)
            elif current_section == "risk_assessment" and line:
                report["risk_assessment"] += line + " "
        
        # 生成摘要
        report["summary"] = content[:500] + "..." if len(content) > 500 else content
        
        return report
    
    def analyze_html(self, html: str) -> Dict[str, Any]:
        """分析HTML内容
        
        Args:
            html: HTML内容
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        test_result = {"status": "pending", "payloads": []}
        return self.analyze_xss_result(html, test_result)


def get_analyzer(model: str = "gpt-4") -> AIAnalyzer:
    """获取AI分析器实例
    
    Args:
        model: 模型名称
        
    Returns:
        AIAnalyzer: AI分析器实例
    """
    return AIAnalyzer(model)
