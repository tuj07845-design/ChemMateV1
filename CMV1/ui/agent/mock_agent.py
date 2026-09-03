# -*- coding: utf-8 -*-
"""Mock Agent —— 按 Agent → Tool → Result 编排一次演示运行。

线程驱动状态机，前端 400ms 轮询 snapshot() 渲染：
    workflow 卡片状态（waiting/running/success/error）+ 耗时 + 一句话结果
    console 日志（[Agent] / [Tool: xxx] 逐条推送）
    result（data_get 的股流数据 + 图片路径 + 报告路径）

真实 Agent 接入时：保留本类的状态/日志/快照协议，
把 TOOL_REGISTRY 换成真实 Tool 即可（见 README）。
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.base import ToolStopped
from tools.mock_data_get import MockDataGetTool
from tools.mock_draw_mat import MockDrawMatTool
from tools.mock_path_finder import MockPathFinderTool
from tools.mock_word_create import MockWordCreateTool

# Tool 注册表：换成真实 Tool 只改这里
TOOL_REGISTRY = {
    "path_finder": MockPathFinderTool(),
    "data_get": MockDataGetTool(),
    "draw_mat": MockDrawMatTool(),
    "word_create": MockWordCreateTool(),
}

# 工作流节点（UI 展示顺序）
STEP_DEFS = [
    ("user_task", "User Task", "用户任务", None),
    ("agent", "Agent", "任务解析", None),
    ("path_finder", "path_finder", "模型文件定位", "path_finder"),
    ("data_get", "data_get", "Aspen 数据获取", "data_get"),
    ("draw_mat", "draw_mat", "MATLAB 绘图", "draw_mat"),
    ("analysis", "Agent Analysis", "结果分析", None),
    ("word_create", "word_create", "报告生成", "word_create"),
    ("completed", "Completed", "任务完成", None),
]


class MockAgent(threading.Thread):
    def __init__(self, task: str, runs_dir: Path):
        super().__init__(daemon=True)
        self.run_id = uuid.uuid4().hex[:8]
        self.task = task
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._t0 = time.monotonic()

        self.run_dir = Path(runs_dir) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.context: dict[str, Any] = {"task": task, "run_dir": str(self.run_dir)}

        self.state: dict[str, Any] = {
            "run_id": self.run_id,
            "task": task,
            "status": "running",
            "elapsed": 0.0,
            "steps": [
                {"key": k, "name": n, "cn": cn, "status": "waiting", "duration": None, "result": ""}
                for k, n, cn, _ in STEP_DEFS
            ],
            "logs": [],
            "result": None,
            "figure": None,
            "reports": {},
        }

    # ---------------- 对外协议 ----------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            snap = dict(self.state)
            snap["steps"] = [dict(s) for s in self.state["steps"]]
            snap["logs"] = list(self.state["logs"])
            snap["reports"] = dict(self.state["reports"])
            return snap

    def request_stop(self) -> None:
        self.stop_event.set()

    def generate_report(self, report_type: str) -> dict:
        """UI 的[生成 Word]/[生成 PPT]按钮调用。"""
        from tools.mock_word_create import generate_report

        res = generate_report(
            self.context.get("task", ""),
            self.context.get("stream") or {},
            self.run_dir,
            report_type,
        )
        if res.get("success"):
            with self._lock:
                self.state["reports"][report_type] = res.get("file_path", "")
            label = "Word" if report_type == "docx" else "PPT"
            self._log("Tool: word_create", f"✓ {label} report generated", ok=True)
        return res

    def redraw_figure(self, seed: int = 0) -> dict:
        """UI 的[重新绘图]按钮调用。"""
        from tools.mock_draw_mat import generate_figure

        path = generate_figure(self.run_dir, seed=seed)
        with self._lock:
            self.state["figure"] = path
        self._log("Tool: draw_mat", "✓ Plot completed (redraw)", ok=True)
        return {"success": True, "figure": path}

    # ---------------- 内部 ----------------

    def _log(self, source: str, text: str, ok: bool | None = None) -> None:
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "source": source,
            "text": text,
            "ok": ok,
        }
        with self._lock:
            self.state["logs"].append(entry)

    def _set_step(self, key: str, status: str, duration: float | None = None, result: str = "") -> None:
        with self._lock:
            for s in self.state["steps"]:
                if s["key"] == key:
                    s["status"] = status
                    if duration is not None:
                        s["duration"] = round(duration, 1)
                    if result:
                        s["result"] = result
                    break

    def _finish(self, status: str, msg: str, ok: bool | None = None) -> None:
        self._log("System", msg, ok=ok)
        with self._lock:
            self.state["status"] = status
            self.state["elapsed"] = round(time.monotonic() - self._t0, 1)

    def run(self) -> None:  # noqa: C901
        try:
            self._set_step("user_task", "success", 0.0, self.task[:36] + ("…" if len(self.task) > 36 else ""))

            # ---- Agent 任务解析 ----
            self._set_step("agent", "running")
            self._log("Agent", "正在分析用户任务……")
            time.sleep(0.9)
            if self.stop_event.is_set():
                return self._abort()
            self._log("Agent", "识别目标：定位模型 → 读取 S10 → 绘图 → 生成报告")
            time.sleep(0.6)
            self._set_step("agent", "success", 1.5, "任务已解析为 4 步 Tool 链")

            # ---- Tool 链 ----
            for key, _name, _cn, tool_key in STEP_DEFS:
                if key == "analysis":
                    self._run_analysis()
                    continue
                if tool_key is None:
                    continue
                if key == "agent":
                    continue
                if self.stop_event.is_set():
                    return self._abort()
                tool = TOOL_REGISTRY[tool_key]
                self._set_step(key, "running")
                t0 = time.monotonic()
                try:
                    res = tool.execute(self.task, self.context, self._log, self.stop_event)
                except ToolStopped:
                    return self._abort()
                except Exception as exc:  # 工具失败 → 全链 Error
                    dur = time.monotonic() - t0
                    self._set_step(key, "error", dur, str(exc)[:60])
                    self._log(f"Tool: {tool_key}", f"✗ {exc}", ok=False)
                    return self._finish("error", f"✗ {tool_key} 执行失败：{exc}", ok=False)
                dur = time.monotonic() - t0
                self._set_step(key, "success", dur, res.get("message", ""))
                data = res.get("data") or {}
                self.context.update(data)
                with self._lock:
                    if "stream" in data:
                        self.state["result"] = data["stream"]
                    if "figure_path" in data:
                        self.state["figure"] = data["figure_path"]
                    reports = data.get("reports")
                    if reports:
                        self.state["reports"].update(reports)
                time.sleep(0.25)

            self._set_step("completed", "success")
            self._finish("completed", "✓ 任务完成", ok=True)
        except ToolStopped:
            self._abort()
        except Exception as exc:  # 兜底
            self._finish("error", f"✗ Agent 异常：{exc}", ok=False)

    def _run_analysis(self) -> None:
        self._set_step("analysis", "running")
        self._log("Agent", "正在分析模拟结果……")
        time.sleep(1.0)
        if self.stop_event.is_set():
            raise ToolStopped
        self._log("Agent", "✓ S10 为液相（VF=0），环己烷摩尔分率 94.8%，符合产品流预期", ok=True)
        time.sleep(0.5)
        self._set_step("analysis", "success", 1.5, "液相产品流，环己烷 94.8%")

    def _abort(self) -> None:
        with self._lock:
            for s in self.state["steps"]:
                if s["status"] == "running":
                    s["status"] = "error"
                    s["result"] = "用户停止"
        self._finish("stopped", "■ 已停止", ok=False)
