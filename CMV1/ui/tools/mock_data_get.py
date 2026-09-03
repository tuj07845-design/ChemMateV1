# -*- coding: utf-8 -*-
"""Mock data_get —— 模拟从 Aspen Plus 读取股流数据。

真实版对应 CMV1/data_get_process_tool_v2.py 的 data_get_process(...)，
返回结构保持一致（stream: 属性 + 组成表），将来直接替换。
数值按 10 万吨/年环己烷量级编造，仅用于 UI 演示。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from .base import LogFn, ToolBase, ToolResult, ToolStopped

# S10 股流 Mock 数据（10 万吨/年 ≈ 12500 kg/h 量级）
STREAM_DATA = {
    "stream": "S10",
    "properties": [
        {"name": "Temperature", "cn": "温度", "value": 89.701043, "unit": "℃", "decimals": 2},
        {"name": "Pressure", "cn": "压力", "value": 1.0, "unit": "bar", "decimals": 2},
        {"name": "Vapor Fraction", "cn": "汽化分率", "value": 0.0, "unit": "-", "decimals": 2},
        {"name": "Mass Flow", "cn": "质量流量", "value": 12495.9, "unit": "kg/h", "decimals": 1},
        {"name": "Mole Flow", "cn": "摩尔流量", "value": 155.31, "unit": "kmol/h", "decimals": 2},
    ],
    "components": ["氢气 H2", "苯 C6H6", "环己烷 C6H12"],
    "mass_flow": {
        "unit": "kg/h",
        "rows": [["氢气 H2", 14.1], ["苯 C6H6", 86.2], ["环己烷 C6H12", 12395.6]],
        "total": 12495.9,
        "decimals": 1,
    },
    "mole_flow": {
        "unit": "kmol/h",
        "rows": [["氢气 H2", 6.99], ["苯 C6H6", 1.10], ["环己烷 C6H12", 147.22]],
        "total": 155.31,
        "decimals": 2,
    },
    "mole_fraction": {
        "unit": "-",
        "rows": [["氢气 H2", 0.0450], ["苯 C6H6", 0.0071], ["环己烷 C6H12", 0.9479]],
        "total": 1.0,
        "decimals": 4,
    },
}

# 执行日志编排（还原真实 Aspen COM 调用的节奏）
_SCRIPT = [
    (0.6, "Starting Aspen Plus...", None),
    (0.5, "✓ Aspen started", True),
    (0.5, "Loading model...", None),
    (0.5, "✓ Model loaded", True),
    (0.7, "Running simulation...", None),
    (0.6, "✓ Simulation completed", True),
    (0.4, "Reading Stream S10...", None),
    (0.3, "✓ Temperature", True),
    (0.25, "✓ Pressure", True),
    (0.25, "✓ Mass Flow", True),
    (0.25, "✓ Mole Flow", True),
    (0.25, "✓ Mole Fraction", True),
]


class MockDataGetTool(ToolBase):
    name = "data_get"
    display_name = "data_get"
    cn_name = "Aspen 数据获取"
    description = "启动 Aspen Plus、载入模型、读取目标股流的 T/P/流量/组成"

    def execute(
        self,
        task: str,
        context: dict[str, Any],
        log: LogFn,
        stop: threading.Event,
    ) -> ToolResult:
        for delay, text, ok in _SCRIPT:
            if stop.is_set():
                raise ToolStopped
            time.sleep(delay)
            log("Tool: data_get", text, ok=ok)

        return ToolResult(
            success=True,
            message="✓ S10 读取完成（T/P/流量/组成）",
            data={"stream": STREAM_DATA},
        )
