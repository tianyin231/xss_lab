"""
任务执行器模块
作用：管理爬虫进程的生命周期，处理进程间通信，并将爬虫产生的数据持久化到数据库。
"""
from __future__ import annotations

import multiprocessing as mp
import threading
import uuid
from datetime import datetime
from typing import Any

from flask import current_app

from server.db import db
from server.events import EventBus
from server.models import Finding, Job, JobStatus, Log, Page
from server.worker import parse_job_spec, run_worker


class JobRunner:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._lock = threading.Lock()
        self._procs: dict[str, mp.Process] = {}
        self._stop: dict[str, mp.Event] = {}

    def create_job(self, target_url: str, max_depth: int, max_pages: int, use_selenium: bool) -> str:
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            target_url=target_url,
            max_depth=max_depth,
            max_pages=max_pages,
            use_selenium=use_selenium,
            status=JobStatus.queued.value,
        )
        db.session.add(job)
        db.session.commit()
        self._bus.publish(job_id, "job", {"status": job.status})
        return job_id

    def start_job(self, job_id: str) -> None:
        app = current_app._get_current_object()
        with self._lock:
            if job_id in self._procs and self._procs[job_id].is_alive():
                return

            job: Job | None = db.session.get(Job, job_id)
            if job is None:
                return

            job.status = JobStatus.running.value
            job.started_at = datetime.now()
            db.session.commit()

            out_queue: mp.Queue = mp.Queue()
            stop_event = mp.Event()
            proc = mp.Process(
                target=run_worker,
                args=(
                    parse_job_spec(
                        {
                            "job_id": job.id,
                            "target_url": job.target_url,
                            "max_depth": job.max_depth,
                            "max_pages": job.max_pages,
                            "use_selenium": job.use_selenium,
                        }
                    ),
                    out_queue,
                    stop_event,
                ),
                daemon=True,
            )
            self._procs[job_id] = proc
            self._stop[job_id] = stop_event

            t = threading.Thread(target=self._consume_events, args=(app, job_id, out_queue), daemon=True)
            t.start()

            proc.start()
            self._bus.publish(job_id, "job", {"status": JobStatus.running.value})

    def stop_job(self, job_id: str) -> None:
        with self._lock:
            ev = self._stop.get(job_id)
            if ev is not None:
                ev.set()
            proc = self._procs.get(job_id)

        if proc is not None and proc.is_alive():
            # 先温和终止
            proc.terminate()
            proc.join(timeout=3.0)
            # 如果还没死，强杀
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)

        job: Job | None = db.session.get(Job, job_id)
        if job is not None and job.status == JobStatus.running.value:
            job.status = JobStatus.stopped.value
            job.finished_at = datetime.now()
            db.session.commit()
            self._bus.publish(job_id, "job", {"status": job.status})

    def _consume_events(self, app: Any, job_id: str, out_queue: mp.Queue) -> None:
        with app.app_context():
            while True:
                try:
                    msg: dict[str, Any] = out_queue.get(timeout=0.5)
                except Exception:
                    proc = self._procs.get(job_id)
                    if proc is None:
                        return
                    if not proc.is_alive():
                        self._finalize_if_needed(job_id=job_id, status=JobStatus.finished.value, error=None)
                        return
                    continue

                msg_type = str(msg.get("type", "log"))
                data = dict(msg.get("data") or {})

                if msg_type == "page":
                    self._persist_page(job_id, data)
                elif msg_type == "finding":
                    self._persist_finding(job_id, data)
                elif msg_type == "log":
                    self._persist_log(job_id, data)
                    self._bus.publish(job_id, "log", data)
                elif msg_type == "error":
                    self._persist_log(job_id, {"message": f"ERROR: {data.get('message')}"})
                    self._bus.publish(job_id, "error", data)
                    self._finalize_if_needed(job_id=job_id, status=JobStatus.failed.value, error=data.get("message"))
                    return
                elif msg_type == "done":
                    self._persist_log(job_id, {"message": "done"})
                    self._bus.publish(job_id, "log", {"message": "done"})
                    self._finalize_if_needed(job_id=job_id, status=JobStatus.finished.value, error=None)
                    return
                else:
                    self._persist_log(job_id, data)
                    self._bus.publish(job_id, msg_type, data)

    def _persist_page(self, job_id: str, data: dict[str, Any]) -> None:
        page = Page(
            job_id=job_id,
            url=str(data.get("url") or ""),
            status_code=int(data.get("status_code") or 0) or None,
            content_type=str(data.get("content_type") or "") or None,
            content=data.get("content") or None,  # 保存HTML源码
            sha256=str(data.get("sha256") or "") or None,
        )
        db.session.add(page)
        db.session.commit()

    def _persist_finding(self, job_id: str, data: dict[str, Any]) -> None:
        finding = Finding(
            job_id=job_id,
            url=str(data.get("url") or ""),
            kind=str(data.get("kind") or "unknown"),
            severity=str(data.get("severity") or "info"),
            title=str(data.get("title") or "Finding"),
            evidence=str(data.get("evidence") or ""),
        )
        db.session.add(finding)
        db.session.commit()

    def _persist_log(self, job_id: str, data: dict[str, Any]) -> None:
        msg = str(data.get("message") or "")
        if not msg:
            return
        log = Log(
            job_id=job_id,
            message=msg,
        )
        db.session.add(log)
        db.session.commit()

    def _finalize_if_needed(self, job_id: str, status: str, error: str | None) -> None:
        job: Job | None = db.session.get(Job, job_id)
        if job is None:
            return
        if job.status not in {JobStatus.running.value, JobStatus.queued.value}:
            return
        job.status = status
        job.error = error
        job.finished_at = datetime.utcnow()
        db.session.commit()
        self._bus.publish(job_id, "job", {"status": job.status, "error": job.error})


_bus = EventBus()
runner = JobRunner(bus=_bus)
bus = _bus
