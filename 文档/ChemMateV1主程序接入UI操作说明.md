# ChemMate V1 主程序接入 UI 操作说明

> 对象：代码小白（你本人）
> 目标：把网页 UI（现在是 Mock 演示）接到真实主程序 agent_main.py，让网页端驱动真实的 Aspen 取数 → MATLAB 绘图 → Word/PPT 报告。
> 前置：重构已完成（tools/agents/memory/config 都可用，python agent_main.py 能跑通真实任务）

## 目录

- 1　现状：UI 用的是「假引擎」（Mock）
- 2　接入原理：换引擎，不换协议
- 3　步骤 1：新建 ui/agent/real_agent.py（真实引擎适配器）
- 4　步骤 2：改 ui/server.py（两处小改，加开关）
- 5　步骤 3：启动与验证
- 6　限制与注意事项（必读）
- 7　回滚方法
- 8　进阶方向（V2 结构化事件）

---

## 1　现状：UI 用的是「假引擎」（Mock）

你的网页 UI（CMV1/ui/）现在跑的是 MockAgent：

```text
浏览器页面 (frontend/)
   │ 任务 → POST /api/run/start
   ▼
server.py (Flask) ──→ MockAgent 线程（假工具：假数据、sleep 模拟、matplotlib 画假图）
   ▲                     │ 每 400ms GET /api/run/state ← snapshot()
   └─────────────────────┘
产物落在 ui/runs/<run_id>/（假图 + 假报告）
```

真实主程序（CMV1/agent_main.py 的 run_agent）已经是「真引擎」，但网页还点不到它。

## 2　接入原理：换引擎，不换协议

MockAgent 和网页之间约定了 4 件事（协议），我们做一个同样遵守协议、内部驱动真实主程序的新类 RealAgent，把引擎换掉：

| 协议 | MockAgent 的实现 | RealAgent 的实现 |
|---|---|---|
| snapshot() | 返回 state 快照（前端轮询渲染） | 完全一样（照抄） |
| request_stop() | 置位 stop_event | 完全一样（照抄） |
| run_dir | ui/runs/<run_id>/ | 完全一样（照抄） |
| run() | 睡几秒假装干活 | 调用 run_agent(task, stop_event=..., log=...) 真干活 |

**本方案最巧妙的一步**：真实工具的产物路径都支持环境变量——

- draw_mat 的画图任务目录：读 CHEMMATE_JOBS_DIR（默认 cwd/jobs）
- report_create 的报告输出目录：读 CHEMMATE_REPORTS_DIR（默认 cwd/reports）

RealAgent 运行前把这两个环境变量指向自己的 run_dir 子目录：

```text
ui/runs/<run_id>/
  ├── jobs/     ← 图的中间产物 + figure.png（真实 MATLAB 画的）
  ├── reports/  ← 真实的 Word/PPT 报告
  └──（前端通过 GET /api/runs/<run_id>/<file> 直接就能展示！）
```

产物天然落在前端可以访问的目录里，server.py 的静态文件接口一个都不用改。


---

## 3　步骤 1：新建 ui/agent/real_agent.py（真实引擎适配器）

在 PyCharm 里对 CMV1/ui/agent 右键 → New → Python File，名字填 real_agent，把下面代码整段贴进去保存：

```python
# -*- coding: utf-8 -*-
"""RealAgent —— UI 的真实引擎适配器。

协议与 MockAgent 完全一致（snapshot / request_stop / run_dir / state），
run() 内部改为驱动 CMV1/agent_main.py 的 run_agent 真实主循环，
让网页端跑真实的 Aspen 取数 → MATLAB 绘图 → Word/PPT 报告。

关键设计：
- 运行前设 CHEMMATE_JOBS_DIR / CHEMMATE_REPORTS_DIR 指向本 run 目录，
  真实工具的图/报告直接产在 ui/runs/<run_id>/ 下，前端即可访问；
- run_agent 的 log 回调（文本行）转成前端日志条目；
- Aspen COM 是单实例：同一时刻只能跑一个 RealAgent。
"""
from __future__ import annotations

import os
import sys
import threading
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

    def _set_status(self, status: str, msg: str, ok: bool | None = None) -> None:
        self._log("System", msg, ok=ok)
        with self._lock:
            self.state["status"] = status
            self.state["elapsed"] = round(time.monotonic() - self._t0, 1)

    def _on_log_line(self, text: str) -> None:
        """run_agent 的 log 回调：把一行文本转成前端日志条目。"""
        line = str(text).strip()
        if not line:
            return
        if "Observation:" in line or line.startswith("模型输出") or line.startswith("--- 循环"):
            self._log("Agent", line[:200])
        elif "错误" in line or "失败" in line or line.startswith("✗"):
            self._log("System", line[:200], ok=False)
        elif line.startswith("任务完成") or line.startswith("用户输入"):
            self._log("Agent", line, ok=True)
        else:
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
                self._set_status("stopped", "■ 已停止", ok=False)
            elif answer:
                with self._lock:
                    self.state["result"] = answer[:500]
                self._set_status("completed", "✓ 任务完成", ok=True)
            else:
                self._set_status("error", "✗ Agent 未返回最终答案", ok=False)
        except Exception as exc:
            self._set_status("error", f"✗ RealAgent 异常：{exc}", ok=False)
```


---

## 4　步骤 2：改 ui/server.py（两处小改，加开关）

打开 CMV1/ui/server.py，只改 2 处，并保留 Mock 可回退：

**改动 1**：把第 27 行（from agent.mock_agent import MockAgent）下面加 5 行：

```python
from agent.mock_agent import MockAgent  # noqa: E402
from agent.real_agent import RealAgent  # noqa: E402

# 开关：设置环境变量 CHEMMATE_UI_REAL=1 时用真实引擎，否则用 Mock
USE_REAL = os.environ.get("CHEMMATE_UI_REAL") == "1"


def _new_agent(task: str, runs_dir: Path):
    cls = RealAgent if USE_REAL else MockAgent
    return cls(task, runs_dir)
```

**改动 2**：把第 55 行的 agent = MockAgent(task, RUNS_DIR) 改成：

```python
agent = _new_agent(task, RUNS_DIR)
```

就这两处。前端、API、产物接口全部不用动。

## 5　步骤 3：启动与验证

**先验证 Mock 没被改坏**：

```bash
cd C:/Users/Fool/Desktop/ChemMateV1工作台/CMV1/ui
python Chem_Mate_V1.py
```

浏览器打开 http://127.0.0.1:8765，随便输个任务，Mock 演示应该照常跑。

**再切真实引擎**（Ctrl+C 停掉后）：

```bash
cd C:/Users/Fool/Desktop/ChemMateV1工作台/CMV1/ui
set CHEMMATE_UI_REAL=1
python Chem_Mate_V1.py
```

浏览器输任务，例如：检查 10万吨环己烷.bkp 全流程有无报错，有则生成带图的 Word 报告

预期现象：
- 右侧 Console 出现真实的 Agent 日志（循环数、模型输出摘要、Observation）
- 任务跑几分钟（真实 Aspen 启动 + MATLAB 出图，比 Mock 慢是正常的）
- 完成后底部 Result 出现真实 MATLAB 图（来自 ui/runs/<run_id>/jobs/）
- 报告区出现真实 Word 文件（来自 ui/runs/<run_id>/reports/）
- 停止按钮在每轮循环之间生效（真实任务不是逐秒可停的）

## 6　限制与注意事项（必读）

1. **Aspen Plus 是单实例**：同一时刻只能跑一个真实任务。别开两个标签页同时点开始，会互相抢 Aspen。
2. **停止不是即时的**：run_agent 只在每轮循环开始前检查 stop_event，最长要等当前一轮工具调用结束（可能是几十秒的 MATLAB 或 COM 调用）。
3. **首次真实运行很慢**：要启动 Aspen（可能弹窗）、连 MATLAB，请耐心等几分钟，不要反复点开始。
4. **环境前提**：真实模式要求 .env 密钥有效、Aspen 与 MATLAB 可用（和 python agent_main.py 命令行跑通是同一套前提）。
5. **重绘/生成报告按钮**：真实模式下返回提示，暂不可用（产物以整次任务为准）。想再出图就重新发起一次任务。
6. **工作流步骤卡片**：真实模式日志驱动，左侧固定步骤卡片不更新属正常现象，看右侧日志和底部结果即可。
7. **日志是文本转换的**：RealAgent 把 run_agent 的打印文本转成前端日志，够用但不精细；V2 可改成结构化事件（见第 8 节）。

## 7　回滚方法

不想用真实模式了，两种方式：

- 临时回退：启动时不设 CHEMMATE_UI_REAL（或设成 0），自动回到 Mock；
- 彻底回退：删掉 ui/agent/real_agent.py，把 server.py 两处改动还原（git checkout 也行）：

```bash
cd C:/Users/Fool/Desktop/ChemMateV1工作台
git checkout -- CMV1/ui/server.py
git rm CMV1/ui/agent/real_agent.py
```

## 8　进阶方向（V2 结构化事件）

现在 RealAgent 靠解析 run_agent 的打印文本转日志，比较脆弱。V2 更优雅的做法：

- 给 run_agent 增加一个可选参数 events=None（回调函数），在关键节点直接回调结构化事件：

```python
events({"type": "round_start", "round": i})
events({"type": "llm_output", "text": llm_output})
events({"type": "tool_call", "tool": tool_name, "kwargs": kwargs})
events({"type": "tool_result", "ok": True, "summary": "..."})
events({"type": "finish", "answer": final_answer})
```

- RealAgent 直接消费这些事件，日志/状态映射更准，还能顺便写进第二层会话记忆（memory/session_store），一行代码两用。
- 同时可以把 run_agent 的产物路径参数化（jobs_root/reports_root 直接传参，替代环境变量），彻底去掉对 cwd 的依赖。

---

## 附：本方案改动文件清单

| 文件 | 动作 | 内容 |
|---|---|---|
| CMV1/ui/agent/real_agent.py | 新建 | RealAgent 类（本说明第 3 节整段代码） |
| CMV1/ui/server.py | 改 2 处 | import + _new_agent 工厂 + run_start 换用工厂 |

改完建议提交：

```bash
cd C:/Users/Fool/Desktop/ChemMateV1工作台
git add -A
git commit -m "ui 接入真实主程序：RealAgent 适配器 + 环境变量开关"
```