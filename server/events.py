from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class JobEvent:
    ts: float
    type: str
    data: dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: dict[str, queue.Queue[JobEvent]] = {}

    def publish(self, job_id: str, type: str, data: dict[str, Any]) -> None:
        evt = JobEvent(ts=time.time(), type=type, data=data)
        with self._lock:
            q = self._queues.get(job_id)
            if q is None:
                q = queue.Queue(maxsize=10_000)
                self._queues[job_id] = q
        try:
            q.put_nowait(evt)
        except queue.Full:
            try:
                _ = q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(evt)
            except queue.Full:
                return

    def stream(self, job_id: str, heartbeat_sec: float = 10.0) -> Iterable[str]:
        with self._lock:
            q = self._queues.get(job_id)
            if q is None:
                q = queue.Queue(maxsize=10_000)
                self._queues[job_id] = q

        while True:
            try:
                evt = q.get(timeout=heartbeat_sec)
                payload = json.dumps(
                    {"ts": evt.ts, "type": evt.type, "data": evt.data},
                    ensure_ascii=False,
                )
                yield f"event: {evt.type}\n"
                yield f"data: {payload}\n\n"
            except queue.Empty:
                yield "event: heartbeat\n"
                yield "data: {}\n\n"
