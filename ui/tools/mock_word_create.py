# -*- coding: utf-8 -*-
"""Mock word_create —— 生成 Word / PPT 报告。

真实版即 CMV1/report_tool.py 的 report_create(...)（排版已按中文阅读习惯），
此处直接复用它渲染 Mock 数据；将来接真实分析结果时只需换 sections 内容来源。
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

from .base import LogFn, ToolBase, ToolResult, ToolStopped, ToolError
from .mock_data_get import STREAM_DATA

# 引入同级的真实渲染器（CMV1/report_tool.py）
_CMV1_DIR = Path(__file__).resolve().parents[2]
if str(_CMV1_DIR) not in sys.path:
    sys.path.insert(0, str(_CMV1_DIR))

try:
    from report_tool import report_create  # type: ignore
    _HAS_REPORT_TOOL = True
except Exception:  # 渲染器不可用时退回纯文案 Mock
    _HAS_REPORT_TOOL = False


def build_sections(task: str, stream: dict) -> list[dict]:
    """把 Mock 股流数据组装成 report_create 的 sections。"""
    secs: list[dict] = []
    secs.append({"type": "heading", "level": 1, "text": "一、任务"})
    secs.append({"type": "paragraph", "text": task})

    secs.append({"type": "heading", "level": 1, "text": "二、股流概况"})
    secs.append({
        "type": "table",
        "headers": ["属性", "数值", "单位"],
        "rows": [
            [f"{p['cn']} {p['name']}", f"{p['value']:.{p['decimals']}f}", p["unit"]]
            for p in stream["properties"]
        ],
    })

    for key, title in (
        ("mass_flow", "三、质量流量"),
        ("mole_flow", "四、摩尔流量"),
        ("mole_fraction", "五、摩尔分率"),
    ):
        blk = stream[key]
        secs.append({"type": "heading", "level": 1, "text": title})
        rows = [[c, f"{v:.{blk['decimals']}f}"] for c, v in blk["rows"]]
        rows.append(["合计", f"{blk['total']:.{blk['decimals']}f}"])
        secs.append({"type": "table", "headers": ["组分", f"数值（{blk['unit']}）"], "rows": rows})

    return secs


def generate_report(
    task: str,
    stream: dict,
    run_dir: str | Path,
    report_type: str = "docx",
) -> dict:
    """生成报告文件，返回 report_create 的统一结果 dict。

    被 Agent 工作流步骤和 UI 的[生成 Word]/[生成 PPT]按钮共用。
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / f"S10_物流分析报告.{report_type}"

    if not _HAS_REPORT_TOOL:
        out.write_text("Word report generated (mock)\n", encoding="utf-8")
        return {"success": True, "file_path": str(out), "message": "Word report generated (mock)"}

    return report_create(
        report_type=report_type,
        title="10万吨环己烷 · S10 物流分析报告（Mock 数据）",
        sections=build_sections(task, stream),
        output_path=str(out),
        author="ChemMate V1 UI",
    )


class MockWordCreateTool(ToolBase):
    name = "word_create"
    display_name = "word_create"
    cn_name = "报告生成"
    description = "把股流数据渲染成 Word/PPT 报告（复用 report_tool 排版）"

    def execute(
        self,
        task: str,
        context: dict[str, Any],
        log: LogFn,
        stop: threading.Event,
    ) -> ToolResult:
        log("Tool: word_create", "Building sections...")
        time.sleep(0.5)
        if stop.is_set():
            raise ToolStopped

        stream = context.get("stream") or STREAM_DATA
        run_dir = context.get("run_dir", ".")
        log("Tool: word_create", "Rendering docx...")
        res = generate_report(task, stream, run_dir, "docx")
        time.sleep(0.3)
        if not res.get("success"):
            raise ToolError(str(res.get("message") or "report_create failed"))
        log("Tool: word_create", "✓ Word report generated", ok=True)

        return ToolResult(
            success=True,
            message="✓ Word 报告已生成",
            data={"reports": {"docx": res.get("file_path", "")}},
        )
