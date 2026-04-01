"""
AI模块初始化文件
"""
from ai.analyzer import get_analyzer, AIAnalyzer
from ai.api import get_ai_analyzer, AIModelAPI

__all__ = [
    "get_analyzer",
    "AIAnalyzer",
    "get_ai_analyzer",
    "AIModelAPI"
]
