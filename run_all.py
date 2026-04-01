"""
XSSLab 一键启动脚本
作用：同时启动前端静态服务器 (web/) 和后端 Flask 服务器 (server/)，并管理它们的生命周期。
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Sequence


def main(argv: Sequence[str]) -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.copy()
    env["PYTHONPATH"] = root + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    backend_cmd = [sys.executable, os.path.join(root, "run_dev.py")]
    frontend_port = str(env.get("FRONTEND_PORT") or "5173")
    frontend_dir = env.get("FRONTEND_DIR") or os.path.join(root, "web")
    frontend_cmd = [sys.executable, "-m", "http.server", frontend_port, "--directory", frontend_dir]

    # 跨平台进程创建：Windows使用start_new_session，Unix使用setsid
    if os.name == 'nt':  # Windows系统
        backend = subprocess.Popen(backend_cmd, cwd=root, env=env, start_new_session=True)
        frontend = subprocess.Popen(frontend_cmd, cwd=root, env=env, start_new_session=True)
    else:  # Unix/Linux系统
        backend = subprocess.Popen(backend_cmd, cwd=root, env=env, preexec_fn=os.setsid)
        frontend = subprocess.Popen(frontend_cmd, cwd=root, env=env, preexec_fn=os.setsid)

    stopping = False

    def stop_children(sig: int) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True

        for p in (frontend, backend):
            try:
                if os.name == 'nt':  # Windows系统
                    # Windows不支持进程组，直接终止进程
                    p.terminate()
                else:  # Unix/Linux系统
                    # 发送信号给整个进程组
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except Exception:
                pass

        deadline = time.time() + 4.0
        while time.time() < deadline:
            if backend.poll() is not None and frontend.poll() is not None:
                return
            time.sleep(0.1)

        for p in (frontend, backend):
            if p.poll() is None:
                try:
                    if os.name == 'nt':  # Windows系统
                        p.kill()
                    else:  # Unix/Linux系统
                        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except Exception:
                    pass

    signal.signal(signal.SIGINT, lambda s, f: stop_children(s))
    signal.signal(signal.SIGTERM, lambda s, f: stop_children(s))

    exit_code = 0
    while True:
        b = backend.poll()
        f = frontend.poll()
        if b is not None or f is not None:
            if not stopping:
                stop_children(signal.SIGTERM)
            exit_code = int(b or f or 0)
            break
        time.sleep(0.2)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

