# -*- coding: utf-8 -*-
"""ChemMate V1 UI — 本地服务器（驱动真实主程序 agent_main.run_agent）。

API：
    GET  /                          前端页面
    POST /api/run/start   {task}    开始一次真实 Agent 运行 → {run_id}
    POST /api/run/stop    {run_id}  请求停止
    GET  /api/run/state?run_id=     全量快照（前端 400ms 轮询）
    GET  /api/runs/<id>/<file>      运行产物（图 / 报告）
    POST /api/redraw     {run_id}   重新绘图
    POST /api/report     {run_id, report_type}  生成 Word/PPT
    POST /api/open       {path}     用系统默认程序打开产物（限 runs 目录内）
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

UI_DIR = Path(__file__).resolve().parent
RUNS_DIR = UI_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)


from agent.real_agent import RealAgent  # noqa: E402

_runs: dict[str, RealAgent] = {}
_runs_lock = threading.Lock()


def _get_agent(run_id: str) -> RealAgent | None:
    with _runs_lock:
        return _runs.get(run_id)


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(UI_DIR / "frontend"),
        static_url_path="/static",
    )

    @app.get("/")
    def index():
        return send_from_directory(UI_DIR / "frontend", "index.html")

    @app.post("/api/run/start")
    def run_start():
        body = request.get_json(silent=True) or {}
        task = str(body.get("task", "")).strip()
        if not task:
            return jsonify(error="task 不能为空"), 400
        agent = RealAgent(task, RUNS_DIR)
        with _runs_lock:
            _runs[agent.run_id] = agent
        agent.start()
        return jsonify(run_id=agent.run_id)

    @app.post("/api/run/stop")
    def run_stop():
        body = request.get_json(silent=True) or {}
        agent = _get_agent(str(body.get("run_id", "")))
        if not agent:
            return jsonify(error="no such run"), 404
        agent.request_stop()
        return jsonify(success=True)

    @app.get("/api/run/state")
    def run_state():
        agent = _get_agent(request.args.get("run_id", ""))
        if not agent:
            return jsonify(error="no such run"), 404
        return jsonify(agent.snapshot())

    @app.get("/api/runs/<run_id>/<path:fname>")
    def run_file(run_id: str, fname: str):
        # 只允许访问 runs/<run_id>/ 内的产物
        directory = (RUNS_DIR / run_id).resolve()
        if not str(directory).startswith(str(RUNS_DIR.resolve())):
            return jsonify(error="forbidden"), 403
        return send_from_directory(directory, fname)

    @app.post("/api/redraw")
    def redraw():
        body = request.get_json(silent=True) or {}
        agent = _get_agent(str(body.get("run_id", "")))
        if not agent:
            return jsonify(error="no such run"), 404
        import random

        return jsonify(agent.redraw_figure(seed=random.randint(0, 9999)))

    @app.post("/api/report")
    def report():
        body = request.get_json(silent=True) or {}
        agent = _get_agent(str(body.get("run_id", "")))
        rt = str(body.get("report_type", "docx"))
        if not agent:
            return jsonify(error="no such run"), 404
        if rt not in ("docx", "pptx"):
            return jsonify(error="report_type 必须是 docx 或 pptx"), 400
        return jsonify(agent.generate_report(rt))

    @app.post("/api/open")
    def open_artifact():
        p = str((request.get_json(silent=True) or {}).get("path", ""))
        target = Path(p).resolve()
        if not str(target).startswith(str(RUNS_DIR.resolve())):
            return jsonify(error="只允许打开 runs 目录内的产物"), 403
        if not target.is_file():
            return jsonify(error="文件不存在"), 404
        os.startfile(str(target))  # noqa: S606（Windows：系统默认程序打开）
        return jsonify(success=True)

    return app
