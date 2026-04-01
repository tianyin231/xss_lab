"""
爬虫进程上下文管理模块
作用：处理主进程与爬虫子进程之间的通信。包含事件推送 (push_event) 和停止信号检测 (get_stop_requested) 等功能，是实现“即点即停”和“实时日志”的关键中转站。
"""
from __future__ import annotations

import multiprocessing as mp
from typing import Any

_OUT_QUEUE: mp.Queue | None = None
_STOP_EVENT: mp.Event | None = None


def init_worker(out_queue: mp.Queue, stop_event: mp.Event) -> None:
    global _OUT_QUEUE, _STOP_EVENT
    _OUT_QUEUE = out_queue
    _STOP_EVENT = stop_event


def push_event(job_id: str, type: str, data: dict[str, Any]) -> None:
    if _OUT_QUEUE is None:
        return
    _OUT_QUEUE.put({"job_id": job_id, "type": type, "data": data})


def get_stop_requested() -> bool:
    if _STOP_EVENT is None:
        return False
    return _STOP_EVENT.is_set()
