from __future__ import annotations

import os
import re
import sys
import threading

import pythoncom
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# ui/agent/real_agent.py 向上三级 = CMV1 根目录
CMV1_DIR = Path(__file__).resolve().parent.parent.parent


class RealAgent(threading.Thread):
    def __init__(self, task: str, runs_dir: Path, max_rounds: int = 30):
        super().__init__(daemon=True)
        self.run_id = uuid.uuid4().hex[:8]
        self.task = task
        self.max_rounds = max_rounds
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._t0 = time.monotonic()

        self.run_dir = Path(runs_dir) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self._round = 0

        self.state: dict[str, Any] = {
            "run_id": self.run_id,
            "task": task,
            "status": "running",
            "elapsed": 0.0,
            "steps": [],
            "logs": [],
            "result": None,
            "figure": None,
            "reports": {},
        }

    # ---------------- 对外协议（与 MockAgent 一致） ----------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            snap = dict(self.state)
            snap["steps"] = [dict(s) for s in self.state["steps"]]
            snap["logs"] = list(self.state["logs"])
            snap["reports"] = dict(self.state["reports"])
            return snap

    def request_stop(self) -> None:
        self.stop_event.set()

    def redraw_figure(self, seed: int = 0) -> dict:
        return {"success": False, "error": "真实模式：请重新发起任务来重绘"}

    def generate_report(self, report_type: str) -> dict:
        return {"success": False, "error": "真实模式：请重新发起任务来生成报告"}

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

    def _upsert_step(self, key: str, name: str, cn: str, status: str = "running", result: str = "") -> None:
        """新增或更新一个 workflow 步骤卡片（前端动态渲染用）。"""
        with self._lock:
            for s in self.state["steps"]:
                if s["key"] == key:
                    s["status"] = status
                    if result:
                        s["result"] = result[:120]
                    return
            self.state["steps"].append(
                {"key": key, "name": name, "cn": cn, "status": status,
                 "duration": None, "result": result[:120]}
            )

    def _set_status(self, status: str, msg: str, ok: bool | None = None) -> None:
        self._log("System", msg, ok=ok)
        with self._lock:
            self.state["status"] = status
            self.state["elapsed"] = round(time.monotonic() - self._t0, 1)

    def _on_log_line(self, *args) -> None:
        """run_agent 的 log 回调：解析文本 → 更新前端日志与动态 workflow 步骤。

        run_agent 内部有的 _emit 调用会传多个位置参数（print 风格），
        这里用 *args 兜底拼接，避免多参导致 TypeError。
        """
        text = " ".join(str(a) for a in args) if args else ""
        line = str(text).strip()
        if not line or line.startswith("Tavily Key"):
            return
        m = re.search(r"--- 循环 (\d+) ---", line)
        if m:
            # 新轮开始：确保 task 卡在，开一张 round 卡
            self._round = int(m.group(1))
            self._upsert_step("task", "User Task", "用户任务", "success")
            self._upsert_step(
                f"round_{self._round}", f"Round {self._round}",
                "Agent 推理与工具调用", "running",
            )
            self._log("Agent", f"第 {self._round} 轮开始")
            return
        if "用户输入" in line:
            self._upsert_step("task", "User Task", "用户任务", "running", "任务已接收")
            self._log("Agent", line[:200])
            return
        am = re.search(r"Action:\s*(\w+)", line)
        if am:
            tool = am.group(1)
            if self._round:
                self._upsert_step(
                    f"round_{self._round}", f"Round {self._round}",
                    "Agent 推理与工具调用", "running", "→ " + tool,
                )
            self._log("Agent", "调用工具: " + tool)
            return
        if line.startswith("模型输出"):
            self._log("Agent", "模型思考中……")
            return
        if "Observation:" in line:
            if self._round:
                self._upsert_step(
                    f"round_{self._round}", f"Round {self._round}",
                    "Agent 推理与工具调用", "running", "✓ 已取回工具结果",
                )
            self._log("Tool", line[:240], ok=True)
            return
        if "任务完成" in line or "最终答案" in line:
            if self._round:
                self._upsert_step(
                    f"round_{self._round}", f"Round {self._round}",
                    "Agent 推理与工具调用", "success", "✓ 任务完成",
                )
            self._log("Agent", line, ok=True)
            return
        if "错误" in line or "失败" in line or line.startswith("✗"):
            self._log("System", line[:200], ok=False)
            return
        self._log("Agent", line[:200])

    def _collect_artifacts(self) -> None:
        """任务结束后扫描 run_dir 下的真实产物，登记给前端展示。"""
        figure = None
        reports: dict[str, str] = {}
        jobs_dir = self.run_dir / "jobs"
        if jobs_dir.is_dir():
            figs = sorted(jobs_dir.glob("*/figure.png"), key=lambda p: p.stat().st_mtime)
            if figs:
                figure = str(figs[-1])
        reps_dir = self.run_dir / "reports"
        if reps_dir.is_dir():
            docxs = sorted(reps_dir.glob("*.docx"), key=lambda p: p.stat().st_mtime)
            pptxs = sorted(reps_dir.glob("*.pptx"), key=lambda p: p.stat().st_mtime)
            if docxs:
                reports["docx"] = str(docxs[-1])
            if pptxs:
                reports["pptx"] = str(pptxs[-1])
        with self._lock:
            if figure:
                self.state["figure"] = figure
            if reports:
                self.state["reports"] = reports

    # ---------------- 主流程 ----------------

    def run(self) -> None:
        # 本线程会通过 COM 调用 Aspen：线程内使用 COM 前必须先初始化
        pythoncom.CoInitialize()
        try:
            # 1. 让真实工具的产物直接产到本 run 目录
            os.environ["CHEMMATE_JOBS_DIR"] = str(self.run_dir / "jobs")
            os.environ["CHEMMATE_REPORTS_DIR"] = str(self.run_dir / "reports")

            # 2. 让 Python 找得到 CMV1 根目录下的包（tools/agents/config）
            if str(CMV1_DIR) not in sys.path:
                sys.path.insert(0, str(CMV1_DIR))

            # 3. 导入并驱动真实主程序
            from agent_main import run_agent  # noqa: E402

            answer = run_agent(
                self.task,
                max_rounds=self.max_rounds,
                stop_event=self.stop_event,
                log=self._on_log_line,
            )

            # 4. 收尾：状态 + 产物登记
            self._collect_artifacts()
            if self.stop_event.is_set():
                self._mark_rounds("error")
                self._set_status("stopped", "■ 已停止", ok=False)
            elif answer:
                with self._lock:
                    self.state["result"] = answer[:2000]
                self._set_status("completed", "✓ 任务完成", ok=True)
            else:
                self._mark_rounds("error")
                self._set_status("error", "✗ Agent 未返回最终答案", ok=False)
        except Exception as exc:
            self._mark_rounds("error")
            self._set_status("error", f"✗ RealAgent 异常：{exc}", ok=False)
        finally:
            pythoncom.CoUninitialize()

    def _mark_rounds(self, status: str) -> None:
        """把仍处于 running 的步骤卡片统一标为指定状态。"""
        with self._lock:
            for s in self.state["steps"]:
                if s["status"] == "running":
                    s["status"] = status
                    if not s.get("result"):
                        s["result"] = "用户停止" if status == "error" else ""